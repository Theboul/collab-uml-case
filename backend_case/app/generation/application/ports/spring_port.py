"""
Puerto de generación Spring Boot (CU10). Aísla a GenerationService del
protocolo concreto usado para hablar con el generador Java (back_generator_uml)
-- hoy HTTP contra un despliegue real (ver HttpSpringAdapter), mañana podría
ser otro transporte sin tocar la capa de aplicación. Mismo criterio de "puerto
por generador" de .claude/rules/fastapi.md: Spring y Postman son dos salidas
reales y distintas, cada una con su propio puerto.
"""

from typing import Any, Protocol


class SpringGeneratorUnavailableError(Exception):
    """El generador Spring Boot (back_generator_uml) no respondió correctamente."""


class SpringGeneratorPort(Protocol):
    async def generate(self, payload: dict[str, Any]) -> bytes:
        """
        Envía el payload {"classes": [...], "relationships": [...]} (forma
        producida por LegacyOutputAdapter.to_legacy_dto) y devuelve los bytes
        del .zip generado. Implementaciones deben traducir cualquier falla de
        transporte (timeout, conexión, HTTP de error) a
        SpringGeneratorUnavailableError -- nunca dejar escapar la excepción cruda
        del cliente HTTP subyacente.
        """
        ...
