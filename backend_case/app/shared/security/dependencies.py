"""
Dependencias de inyección de FastAPI para extracción y validación de usuarios autenticados.
"""

import sys
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import async_session_factory, get_db_session
from .models import UserORM
from .tokens import decode_access_token

if "backend_case.app.shared.security.dependencies" not in sys.modules:
    sys.modules["backend_case.app.shared.security.dependencies"] = sys.modules[__name__]
if "app.shared.security.dependencies" not in sys.modules:
    sys.modules["app.shared.security.dependencies"] = sys.modules[__name__]

http_bearer = HTTPBearer(auto_error=False)

WS_BEARER_SUBPROTOCOL = "bearer"
WS_UNAUTHORIZED_CLOSE_CODE = 4401


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
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_TOKEN_EXPIRED",
                "message": "El token de acceso ha expirado. Renueve su sesión.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "AUTH_INVALID_TOKEN",
                "message": "Token de autenticación inválido o corrupto.",
            },
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

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
    session: AsyncSession,
    token: str | None = None,
) -> UserORM | None:
    """
    Variante de `get_current_user_optional` para conexiones WebSocket. Recibe el token ya
    extraído del handshake (ver `get_ws_bearer_token`) y replica la misma semántica de
    "None si no hay token o el token es inválido": nunca levanta excepción.
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


def get_ws_bearer_token(websocket: WebSocket) -> str | None:
    """
    JWT del cliente en `Sec-WebSocket-Protocol: bearer, <jwt>`. Un WebSocket del navegador no
    puede enviar `Authorization`, y en la query string el token quedaría en logs e historial.
    """
    offered: list[str] = websocket.scope.get("subprotocols", [])
    if len(offered) == 2 and offered[0] == WS_BEARER_SUBPROTOCOL:
        return offered[1]
    return None


def ws_accept_subprotocol(websocket: WebSocket) -> str | None:
    """Subprotocolo a devolver en `accept()`: el navegador exige que sea uno de los ofrecidos."""
    offered: list[str] = websocket.scope.get("subprotocols", [])
    return WS_BEARER_SUBPROTOCOL if WS_BEARER_SUBPROTOCOL in offered else None


async def authenticate_ws_user(websocket: WebSocket) -> UserORM | None:
    """Usuario del handshake o None. Sesión de DB de vida corta (regla de WS en fastapi.md)."""
    async with async_session_factory() as session:
        return await get_current_user_optional_ws(session, get_ws_bearer_token(websocket))
