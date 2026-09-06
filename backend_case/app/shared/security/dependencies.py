"""
Dependencias de inyección de FastAPI para extracción y validación de usuarios autenticados.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db_session
from .models import UserORM
from .tokens import decode_access_token

http_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserORM:
    """
    Exige un Access Token JWT válido en la cabecera Authorization: Bearer.
    Retorna la entidad UserORM activa.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_REQUIRED",
                "message": "Se requiere autenticación para acceder a este recurso.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(auth.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_TOKEN_EXPIRED",
                "message": "El token de acceso ha expirado. Renueve su sesión.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_INVALID_TOKEN",
                "message": "Token de autenticación inválido o corrupto.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_INVALID_TOKEN", "message": "Payload de token sin sujeto 'sub'."},
        )

    result = await session.execute(select(UserORM).where(UserORM.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_USER_DISABLED",
                "message": "Usuario no encontrado o cuenta desactivada.",
            },
        )

    return user


async def get_current_user_optional(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserORM | None:
    """
    Retorna el usuario autenticado si existe un token válido, o None en caso contrario.
    """
    if not auth or not auth.credentials:
        return None
    try:
        return await get_current_user(auth, session)
    except HTTPException:
        return None
