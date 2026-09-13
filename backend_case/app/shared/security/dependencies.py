"""
Dependencias de inyección de FastAPI para extracción y validación de usuarios autenticados.
"""

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Query, status
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


async def get_current_user_optional_ws(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    token: Annotated[str | None, Query()] = None,
) -> UserORM | None:
    """
    Variante de `get_current_user_optional` para conexiones WebSocket: un WS del
    navegador no puede mandar el header `Authorization` en el handshake, así que el
    JWT viaja como query param (`?token=...`) en su lugar. Sin precedente previo en
    el proyecto (ni siquiera en el stack legacy de señalización WebRTC, que no
    autentica en absoluto) — se replica la misma semántica de "None si no hay token
    o el token es inválido", nunca levanta excepción.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await session.execute(select(UserORM).where(UserORM.id == user_id))
    user = result.scalar_one_or_none()
    return user if user and user.is_active else None
