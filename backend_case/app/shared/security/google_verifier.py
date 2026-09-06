"""
Verificación de Google ID Tokens (OpenID Connect).
Valida firma, expiración y audiencia de credenciales devueltas por Google Identity Services.
"""

import os
from typing import Any

import httpx

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleTokenError(Exception):
    """Lanzado cuando el ID Token de Google es inválido o no puede ser verificado."""


async def verify_google_token(credential: str) -> dict[str, Any]:
    """
    Verifica el token OIDC emitido por Google.
    Retorna un diccionario con claims { sub, email, name, picture, email_verified }.
    """
    if not credential:
        raise GoogleTokenError("El token de credencial de Google está vacío.")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                GOOGLE_TOKENINFO_URL,
                params={"id_token": credential},
            )
            if response.status_code != 200:
                raise GoogleTokenError(
                    f"Token de Google rechazado por el emisor (HTTP {response.status_code})"
                )

            payload = response.json()

            # Validar audiencia (si GOOGLE_CLIENT_ID está configurado)
            if GOOGLE_CLIENT_ID and payload.get("aud") != GOOGLE_CLIENT_ID:
                raise GoogleTokenError("La audiencia 'aud' del token no coincide con GOOGLE_CLIENT_ID")

            sub = payload.get("sub")
            email = payload.get("email")

            if not sub or not email:
                raise GoogleTokenError("El token de Google no contiene 'sub' o 'email'")

            return {
                "sub": str(sub),
                "email": str(email).lower(),
                "name": payload.get("name") or str(email).split("@")[0],
                "picture": payload.get("picture"),
                "email_verified": payload.get("email_verified", "true") == "true",
            }
    except httpx.RequestError as e:
        raise GoogleTokenError(f"Error de red al contactar servidores de Google: {e}") from e
