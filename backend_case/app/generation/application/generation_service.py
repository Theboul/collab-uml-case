"""
Servicio de aplicación para CU10: generar un backend Spring Boot real a partir
del modelo UML persistido de un lienzo.

Reutiliza exactamente lo que el análisis de CU10 identificó como ya existente
y funcional (nada de esto se toca ni se reimplementa):
- CanvasService (modeling) para cargar el lienzo y resolver el rol del
  solicitante -- mismo mecanismo de acceso que el resto de endpoints de canvas
  (ver GET /{canvas_id} y POST /{canvas_id}/export/xmi en modeling/interoperability).
- UMLValidator (core/uml_domain) para la validez semántica UML de base.
- SpringCompatibilityValidator (core/uml_domain) para las reglas específicas
  del perfil Spring Boot v1 (ej. VGEN-SB-01: herencia múltiple no soportada).
- LegacyOutputAdapter.to_legacy_dto para construir el payload {classes,
  relationships} en la forma exacta que espera back_generator_uml.

Lo único nuevo acá es la orquestación: cargar -> validar -> transformar ->
invocar al puerto de generación -> devolver el .zip.
"""

from fastapi import HTTPException, status

from backend_case.app.generation.application.ports.spring_port import SpringGeneratorPort
from backend_case.app.modeling.application.canvas_service import CanvasService
from core.uml_domain.adapters.legacy_output_adapter import LegacyOutputAdapter
from core.uml_domain.exceptions import UmlValidationError, UnsupportedGenerationFeature
from core.uml_domain.validation import (
    SpringCompatibilityValidator,
    UMLValidator,
    ValidationSeverity,
)

_ACCESS_FORBIDDEN_DETAIL = {
    "code": "CANVAS_ACCESS_FORBIDDEN",
    "message": (
        "No tenés acceso a este lienzo. Unite con el código de acceso o el enlace de invitación."
    ),
}

_TARGET_GENERATOR = "spring-boot-v1"


class GenerationService:
    def __init__(self, canvas_service: CanvasService, spring_port: SpringGeneratorPort) -> None:
        self.canvas_service = canvas_service
        self.spring_port = spring_port
        self.uml_validator = UMLValidator()
        self.spring_validator = SpringCompatibilityValidator()

    async def generar_spring_boot(
        self, canvas_id: str, user_id: str | None = None
    ) -> tuple[bytes, str]:
        """
        CU10: genera el backend Spring Boot del modelo persistido del lienzo.
        Solo lectura -- no incrementa la versión del canvas. Devuelve
        (zip_bytes, filename_sugerido).
        """
        res = await self.canvas_service.obtener_lienzo(canvas_id, user_id=user_id)
        if res.role == "INVITADO":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_FORBIDDEN_DETAIL
            )

        modelo = res.lienzo.modelo

        resultado_uml = self.uml_validator.validate(modelo)
        if not resultado_uml.is_valid:
            mensajes = "; ".join(i.message for i in resultado_uml.errors)
            raise UmlValidationError(
                f"El modelo del lienzo no pasa la validación semántica UML: {mensajes}"
            )

        resultado_spring = self.spring_validator.validate_compatibility(modelo)
        if not resultado_spring.is_valid:
            mensajes_spring = "; ".join(
                i.message for i in resultado_spring.issues if i.severity == ValidationSeverity.ERROR
            )
            raise UnsupportedGenerationFeature(
                "El modelo usa una característica que el generador Spring Boot v1 no soporta: "
                f"{mensajes_spring}"
            )

        transformation = LegacyOutputAdapter.to_legacy_dto(modelo, _TARGET_GENERATOR)
        zip_bytes = await self.spring_port.generate(transformation.payload)

        filename = f"{modelo.name or 'backend'}-spring-boot.zip"
        return zip_bytes, filename
