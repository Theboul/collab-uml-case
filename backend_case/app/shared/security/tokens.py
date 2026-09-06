"""
Gestión de Access Tokens (JWT) y Refresh Tokens criptográficos.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "schemacraft_super_secret_jwt_key_2026_dev_only")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(
    user_id: str,
    email: str,
    full_name: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crea un token JWT firmado para autorización en peticiones HTTP y WebSockets.
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "fullName": full_name,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decodifica y valida la firma y expiración del Access Token.
    Lanza jwt.PyJWTError si el token es inválido o ha expirado.
    """
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def generate_refresh_token() -> str:
    """
    Genera un refresh token aleatorio de alta entropía (32 bytes urlsafe).
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw_token: str) -> str:
    """
    Calcula el hash SHA-256 del refresh token para almacenarlo seguro en base de datos.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
