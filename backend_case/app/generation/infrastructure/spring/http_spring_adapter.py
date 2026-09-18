"""
Adaptador real del puerto SpringGeneratorPort: llama por HTTP al generador
Java (back_generator_uml), expuesto en producción en GENERATOR_SPRING_URL
(ver front_generador_bd/src/environments/environment.ts -- endpoint_java,
mismo despliegue que ya usa el flujo legacy actual del frontend).
"""

import os
from typing import Any

import httpx

from backend_case.app.generation.application.ports.spring_port import (
    SpringGeneratorUnavailableError,
)

GENERATOR_SPRING_URL = os.getenv("GENERATOR_SPRING_URL", "https://spring-sw1.fournext.me")

_DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class HttpSpringAdapter:
    def __init__(
        self, base_url: str = GENERATOR_SPRING_URL, timeout: httpx.Timeout = _DEFAULT_TIMEOUT
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def generate(self, payload: dict[str, Any]) -> bytes:
        url = f"{self._base_url}/generate"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SpringGeneratorUnavailableError(
                "El generador de backend Spring Boot no respondió a tiempo."
            ) from exc
        except httpx.ConnectError as exc:
            raise SpringGeneratorUnavailableError(
                "No se pudo conectar con el generador de backend Spring Boot."
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise SpringGeneratorUnavailableError(
                "El generador de backend Spring Boot devolvió un error "
                f"({exc.response.status_code})."
            ) from exc
        return response.content
