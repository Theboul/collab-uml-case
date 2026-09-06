"""
Servicio de Aplicación de Autenticación (AuthService).
Implementa la lógica de registro, inicio de sesión por contraseña/Google,
rotación de sesiones y revocación (logout).
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .google_verifier import (
    GoogleTokenError,
    verify_google_token,
)
from .hasher import hash_password, verify_password
from .models import (
    UserIdentityORM,
    UserORM,
    UserSessionORM,
)
from .schemas import (
    AuthResponse,
    UserDto,
    UserProfileResponse,
)
from .tokens import (
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


class AuthService:
    """
    Gestiona la identidad unificada de usuarios, sesiones y emisión de tokens.
    """

    @staticmethod
    async def register_with_password(
        session: AsyncSession,
        email: str,
        password: str,
        full_name: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthResponse, str]:
        """
        Registra una nueva cuenta con correo y contraseña.
        Retorna (AuthResponse, raw_refresh_token).
        """
        clean_email = email.strip().lower()

        # Verificar si el correo ya existe
        existing = await session.execute(select(UserORM).where(UserORM.email == clean_email))
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "AUTH_EMAIL_ALREADY_EXISTS",
                    "message": "Ya existe una cuenta registrada con este correo electrónico.",
                },
            )

        # Crear User
        user = UserORM(
            email=clean_email,
            full_name=full_name.strip(),
            is_active=True,
            is_verified=False,
        )
        session.add(user)
        await session.flush()

        # Crear Identidad de tipo password
        pwd_hash = hash_password(password)
        identity = UserIdentityORM(
            user_id=user.id,
            provider="password",
            provider_user_id=clean_email,
            password_hash=pwd_hash,
        )
        session.add(identity)

        # Crear Sesión y tokens
        access_token, raw_refresh_token = await AuthService._create_session_tokens(
            session=session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await session.commit()

        auth_resp = AuthResponse(
            accessToken=access_token,
            user=UserDto(
                id=user.id,
                email=user.email,
                fullName=user.full_name,
                avatarUrl=user.avatar_url,
            ),
        )
        return auth_resp, raw_refresh_token

    @staticmethod
    async def login_with_password(
        session: AsyncSession,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthResponse, str]:
        """
        Inicia sesión mediante credenciales de correo y contraseña.
        """
        clean_email = email.strip().lower()

        result = await session.execute(
            select(UserIdentityORM)
            .options(selectinload(UserIdentityORM.user))
            .where(
                UserIdentityORM.provider == "password",
                UserIdentityORM.provider_user_id == clean_email,
            )
        )
        identity = result.scalar_one_or_none()

        if not identity or not identity.password_hash or not identity.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTH_INVALID_CREDENTIALS",
                    "message": "Correo o contraseña incorrectos.",
                },
            )

        if not verify_password(password, identity.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTH_INVALID_CREDENTIALS",
                    "message": "Correo o contraseña incorrectos.",
                },
            )

        user = identity.user
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "AUTH_ACCOUNT_DISABLED",
                    "message": "Esta cuenta ha sido desactivada.",
                },
            )

        access_token, raw_refresh_token = await AuthService._create_session_tokens(
            session=session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await session.commit()

        auth_resp = AuthResponse(
            accessToken=access_token,
            user=UserDto(
                id=user.id,
                email=user.email,
                fullName=user.full_name,
                avatarUrl=user.avatar_url,
            ),
        )
        return auth_resp, raw_refresh_token

    @staticmethod
    async def login_with_google(
        session: AsyncSession,
        credential: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthResponse, str]:
        """
        Inicia sesión o vincula cuenta mediante Google ID Token (OIDC).
        """
        try:
            google_data = await verify_google_token(credential)
        except GoogleTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "AUTH_GOOGLE_TOKEN_INVALID", "message": str(e)},
            )

        sub = google_data["sub"]
        email = google_data["email"]
        name = google_data["name"]
        picture = google_data.get("picture")

        # 1. Buscar si la identidad de Google ya existe
        result = await session.execute(
            select(UserIdentityORM)
            .options(selectinload(UserIdentityORM.user))
            .where(
                UserIdentityORM.provider == "google",
                UserIdentityORM.provider_user_id == sub,
            )
        )
        identity = result.scalar_one_or_none()

        if identity and identity.user:
            user = identity.user
        else:
            # 2. Si no existe identidad google, buscar si el usuario ya existe por email (Account Linking)
            user_res = await session.execute(select(UserORM).where(UserORM.email == email))
            user = user_res.scalar_one_or_none()

            if user:
                # Vincular identidad de Google al usuario existente
                new_identity = UserIdentityORM(
                    user_id=user.id,
                    provider="google",
                    provider_user_id=sub,
                )
                session.add(new_identity)
                if not user.avatar_url and picture:
                    user.avatar_url = picture
                user.is_verified = True
            else:
                # 3. Usuario totalmente nuevo
                user = UserORM(
                    email=email,
                    full_name=name,
                    avatar_url=picture,
                    is_active=True,
                    is_verified=True,
                )
                session.add(user)
                await session.flush()

                new_identity = UserIdentityORM(
                    user_id=user.id,
                    provider="google",
                    provider_user_id=sub,
                )
                session.add(new_identity)

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "AUTH_ACCOUNT_DISABLED", "message": "Cuenta desactivada."},
            )

        access_token, raw_refresh_token = await AuthService._create_session_tokens(
            session=session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await session.commit()

        auth_resp = AuthResponse(
            accessToken=access_token,
            user=UserDto(
                id=user.id,
                email=user.email,
                fullName=user.full_name,
                avatarUrl=user.avatar_url,
            ),
        )
        return auth_resp, raw_refresh_token

    @staticmethod
    async def refresh_session(
        session: AsyncSession,
        raw_refresh_token: str | None,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[AuthResponse, str]:
        """
        Valida y rota un refresh token emitiendo un nuevo Access Token.
        """
        if not raw_refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTH_SESSION_EXPIRED",
                    "message": "Cookie de sesión ausente o expirada.",
                },
            )

        token_hash = hash_refresh_token(raw_refresh_token)
        now = datetime.now(timezone.utc)

        result = await session.execute(
            select(UserSessionORM)
            .options(selectinload(UserSessionORM.user))
            .where(
                UserSessionORM.refresh_token_hash == token_hash,
                UserSessionORM.expires_at > now,
            )
        )
        user_session = result.scalar_one_or_none()

        if not user_session or not user_session.user or not user_session.user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTH_SESSION_EXPIRED",
                    "message": "Sesión inválida o expirada. Inicie sesión nuevamente.",
                },
            )

        user = user_session.user

        # Rotación de Refresh Token (destruir el anterior y crear uno nuevo)
        await session.delete(user_session)

        new_access_token, new_refresh_token = await AuthService._create_session_tokens(
            session=session,
            user=user,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        await session.commit()

        auth_resp = AuthResponse(
            accessToken=new_access_token,
            user=UserDto(
                id=user.id,
                email=user.email,
                fullName=user.full_name,
                avatarUrl=user.avatar_url,
            ),
        )
        return auth_resp, new_refresh_token

    @staticmethod
    async def logout(
        session: AsyncSession,
        raw_refresh_token: str | None,
    ) -> None:
        """
        Invalida la sesión activa en el servidor eliminándola de user_sessions.
        """
        if raw_refresh_token:
            token_hash = hash_refresh_token(raw_refresh_token)
            await session.execute(
                delete(UserSessionORM).where(UserSessionORM.refresh_token_hash == token_hash)
            )
            await session.commit()

    @staticmethod
    async def get_user_profile(
        session: AsyncSession,
        user_id: str,
    ) -> UserProfileResponse:
        """
        Retorna los detalles del usuario autenticado y sus métodos de acceso vinculados.
        """
        result = await session.execute(
            select(UserORM)
            .options(selectinload(UserORM.identities))
            .where(UserORM.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "AUTH_USER_NOT_FOUND", "message": "Usuario no encontrado."},
            )

        identities_list = [id_item.provider for id_item in (user.identities or [])]

        return UserProfileResponse(
            id=user.id,
            email=user.email,
            fullName=user.full_name,
            avatarUrl=user.avatar_url,
            identities=identities_list,
            isVerified=user.is_verified,
        )

    @staticmethod
    async def _create_session_tokens(
        session: AsyncSession,
        user: UserORM,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[str, str]:
        """
        Auxiliar interno: genera JWT Access Token y persiste Refresh Token hasheado.
        """
        access_token = create_access_token(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
        )
        raw_refresh_token = generate_refresh_token()
        refresh_hash = hash_refresh_token(raw_refresh_token)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

        new_session = UserSessionORM(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            user_agent=user_agent[:255] if user_agent else None,
            ip_address=ip_address[:45] if ip_address else None,
            expires_at=expires_at,
        )
        session.add(new_session)
        await session.flush()

        return access_token, raw_refresh_token
