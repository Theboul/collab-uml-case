"""
Rutas API v2 para CU10: generar un backend Spring Boot real a partir del
modelo UML persistido de un lienzo.
"""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status

from backend_case.app.generation.application.generation_service import GenerationService
from backend_case.app.generation.application.ports.spring_port import (
    SpringGeneratorUnavailableError,
)
from backend_case.app.shared.deps import get_generation_service

from ...shared.security.dependencies import get_current_user_optional
from ...shared.security.models import UserORM

router = APIRouter(prefix="/canvases", tags=["generation"])

GenerationServiceDep = Annotated[GenerationService, Depends(get_generation_service)]
CurrentUserOptionalDep = Annotated[UserORM | None, Depends(get_current_user_optional)]


def _content_disposition(filename: str) -> str:
    """
    El nombre del lienzo (y por lo tanto del .zip) puede tener tildes/ñ --
    un header HTTP no admite esos bytes crudos en el parámetro `filename`
    (RFC 6266/2616 exige latin-1/ASCII ahí). Se manda un fallback ASCII para
    clientes viejos y el nombre real percent-encoded en UTF-8 vía
    `filename*` (RFC 5987), que es lo que usan los navegadores modernos.
    """
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "backend-spring-boot.zip"
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(filename)}"


@router.post("/{canvas_id}/generation/spring")
async def generate_spring_backend(
    canvas_id: str,
    service: GenerationServiceDep,
    current_user: CurrentUserOptionalDep = None,
) -> Response:
    """
    CU10: genera y devuelve el .zip de un backend Spring Boot a partir del
    modelo UML persistido del lienzo. Solo lectura (no incrementa version),
    mismo control de acceso que GET /{canvas_id}. Valida con UMLValidator y
    SpringCompatibilityValidator antes de generar -- si el modelo no tiene
    ninguna clase, tiene errores bloqueantes o usa una característica no
    soportada por el generador, rechaza con 422/400 explícito y nunca llega
    a invocar al generador Java. Si el generador Java está caído o no responde a tiempo,
    devuelve 503 explícito -- nunca deja escapar la excepción del cliente
    HTTP subyacente como 500 genérico.
    """
    user_id = str(current_user.id) if current_user else None
    try:
        zip_bytes, filename = await service.generar_spring_boot(canvas_id, user_id=user_id)
    except SpringGeneratorUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "SPRING_GENERATOR_UNAVAILABLE", "message": str(exc)},
        ) from exc

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": _content_disposition(filename)},
    )
