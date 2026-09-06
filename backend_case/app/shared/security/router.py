"""
Router de FastAPI para endpoints de Autenticación, Sesiones e Identidad.
Convención de rutas: /api/v2/auth/...
"""

import os
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db_session
from .dependencies import get_current_user
from .models import UserORM
from .schemas import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    UserProfileResponse,
)
from .service import AuthService

COOKIE_NAME = "sc_refresh_token"
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 días
COOKIE_PATH = "/api/v2/auth"

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Configura la cookie HttpOnly con flags de seguridad."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=False,  # Permitir HTTP en localhost dev; en prod activar Secure=True vía reverse proxy
        samesite="lax",
        path=COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Invalida y destruye la cookie de sesión."""
    response.delete_cookie(key=COOKIE_NAME, path=COOKIE_PATH)


@router.get(
    "/config",
    summary="Configuración pública de autenticación para clientes frontend",
)
async def get_public_auth_config() -> dict[str, str]:
    """
    Retorna configuración pública (como el Google Client ID) leída desde el entorno (.env).
    Permite que el frontend no tenga que hardcodear credenciales en archivos .ts.
    """
    return {
        "googleClientId": os.getenv("GOOGLE_CLIENT_ID", ""),
    }


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registro de usuario con correo y contraseña",
)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    auth_resp, refresh_token = await AuthService.register_with_password(
        session=session,
        email=str(payload.email),
        password=payload.password,
        full_name=payload.fullName,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp


@router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Inicio de sesión con correo y contraseña",
)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    auth_resp, refresh_token = await AuthService.login_with_password(
        session=session,
        email=str(payload.email),
        password=payload.password,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp


@router.post(
    "/google",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Autenticación con Google Identity Services (OIDC)",
)
async def login_google(
    request: Request,
    response: Response,
    payload: GoogleAuthRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    auth_resp, refresh_token = await AuthService.login_with_google(
        session=session,
        credential=payload.credential,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, refresh_token)
    return auth_resp


@router.post(
    "/refresh",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="Renovación de sesión y rotación de Refresh Token",
)
async def refresh_session(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    sc_refresh_token: Annotated[str | None, Cookie()] = None,
) -> AuthResponse:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None

    auth_resp, new_refresh_token = await AuthService.refresh_session(
        session=session,
        raw_refresh_token=sc_refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    _set_refresh_cookie(response, new_refresh_token)
    return auth_resp


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cierre de sesión y revocación en servidor",
)
async def logout(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    sc_refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    await AuthService.logout(session, sc_refresh_token)
    _clear_refresh_cookie(response)


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtener perfil del usuario autenticado actual",
)
async def get_my_profile(
    current_user: Annotated[UserORM, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserProfileResponse:
    return await AuthService.get_user_profile(session, current_user.id)
