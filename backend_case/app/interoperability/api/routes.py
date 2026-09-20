"""
Rutas API v2 para CU8: Importar/Exportar modelos UML (XMI 1.1 / UML 1.3, Enterprise Architect).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ConfigDict

from backend_case.app.application.mappers import ValidationResultMapper
from backend_case.app.interoperability.application.xmi_import_service import (
    importar_xmi_a_lienzo_nuevo,
)
from backend_case.app.interoperability.application.xmi_mapping import (
    XmiParseError,
    build_xmi_document,
    find_unsupported_export_warnings,
)
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.schemas.canvas import CanvasDetailSchema, to_detail_schema
from backend_case.app.schemas.uml import ValidationIssueSchema, ValidationResponseSchema
from backend_case.app.shared.deps import get_canvas_service
from backend_case.app.shared.security.dependencies import get_current_user_optional
from backend_case.app.shared.security.models import UserORM
from core.uml_domain.validation import UMLValidator

router = APIRouter(prefix="/canvases", tags=["interoperability"])

CanvasServiceDep = Annotated[CanvasService, Depends(get_canvas_service)]
CurrentUserOptionalDep = Annotated[UserORM | None, Depends(get_current_user_optional)]

_ACCESS_FORBIDDEN_DETAIL = {
    "code": "CANVAS_ACCESS_FORBIDDEN",
    "message": (
        "No tenés acceso a este lienzo. Unite con el código de acceso o el enlace de invitación."
    ),
}


class ImportXmiResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    canvas: CanvasDetailSchema
    validation: ValidationResponseSchema


@router.post("/import", response_model=ImportXmiResponse, status_code=status.HTTP_201_CREATED)
async def import_xmi(
    service: CanvasServiceDep,
    file: Annotated[UploadFile, File()],
    current_user: CurrentUserOptionalDep = None,
) -> ImportXmiResponse:
    """
    CU8: Importa un archivo XMI 1.1/UML 1.3 (Enterprise Architect) y crea un lienzo
    nuevo a partir de él. Acepta anónimos igual que POST /canvases (CU1). Valida con
    UMLValidator (CU9) antes de persistir — si hay errores de dominio, no persiste nada.
    """
    xmi_bytes = await file.read()
    user_id = str(current_user.id) if current_user else None
    try:
        saved, resultado, warnings = await importar_xmi_a_lienzo_nuevo(
            service, xmi_bytes, owner_id=user_id
        )
    except XmiParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "XMI_PARSE_ERROR", "message": str(exc), "details": []},
        ) from exc

    validation_schema = ValidationResultMapper.to_schema(resultado)
    for w in warnings:
        validation_schema.warnings.append(
            ValidationIssueSchema(
                code=w.code,
                message=w.message,
                severity="WARNING",
                elementId=w.element_id,
            )
        )

    if saved is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "XMI_INVALID_MODEL",
                "message": "El modelo importado no pasa la validación semántica UML.",
                "details": [e.model_dump() for e in validation_schema.errors],
            },
        )

    return ImportXmiResponse(
        canvas=to_detail_schema(saved.lienzo, saved.version, saved.owner_id, saved.room_name),
        validation=validation_schema,
    )


@router.get("/{canvas_id}/export/xmi")
async def export_xmi(
    canvas_id: str,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
) -> Response:
    """
    CU8: Exporta el modelo persistido del lienzo a XMI 1.1/UML 1.3 (Enterprise
    Architect). Solo lectura (no incrementa version), mismo control de acceso que
    GET /{canvas_id}. Valida con UMLValidator (CU9) antes de convertir — si el
    modelo tiene errores bloqueantes, rechaza el export con 422 (mismo criterio
    que import: nunca se entrega un XMI que no "conserva la semántica soportada").
    """
    user_id = str(current_user.id) if current_user else None
    res = await service.obtener_lienzo(canvas_id, user_id=user_id)
    if res.role == "INVITADO":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=_ACCESS_FORBIDDEN_DETAIL)

    resultado = UMLValidator().validate(res.lienzo.modelo)
    if not resultado.is_valid:
        validation_schema = ValidationResultMapper.to_schema(resultado)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "XMI_EXPORT_INVALID_MODEL",
                "message": "El modelo del lienzo no pasa la validación semántica UML.",
                "details": [e.model_dump() for e in validation_schema.errors],
            },
        )

    export_warnings = find_unsupported_export_warnings(res.lienzo.modelo)

    xmi_bytes = build_xmi_document(res.lienzo)
    filename = f"{res.lienzo.modelo.name or 'modelo'}.xmi"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if export_warnings:
        # Sin cambiar el contrato (sigue siendo un archivo, no JSON): se hace
        # explícita la pérdida de semántica en un header, no en el cuerpo.
        headers["X-Xmi-Warnings"] = ",".join(w.code for w in export_warnings)
    return Response(
        content=xmi_bytes,
        media_type="application/xml",
        headers=headers,
    )
