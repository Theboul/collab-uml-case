"""
CU8: orquesta el import de un archivo XMI hacia un lienzo nuevo persistido.
Reutiliza UMLValidator (CU9) antes de persistir: nunca guarda un modelo con errores.
"""

from backend_case.app.interoperability.application.xmi_mapping import (
    XmiImportWarning,
    parse_xmi_document,
)
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasResult
from core.uml_domain.model import Lienzo
from core.uml_domain.validation import UMLValidator, ValidationResult


async def importar_xmi_a_lienzo_nuevo(
    service: CanvasService,
    xmi_bytes: bytes,
    owner_id: str | None,
) -> tuple[CanvasResult | None, ValidationResult, list[XmiImportWarning]]:
    """
    CU8: parsea un XMI real de Enterprise Architect y lo persiste como lienzo nuevo
    (mismo espíritu que CU1: crea, no mezcla con un lienzo existente). Puede lanzar
    XmiParseError (XML malformado) — el router la traduce a 422.

    Si UMLValidator encuentra errores de dominio, no persiste nada y devuelve
    (None, resultado, warnings) para que el router responda 422 con el reporte.
    """
    model, positions, warnings = parse_xmi_document(xmi_bytes)

    resultado = UMLValidator().validate(model)
    if not resultado.is_valid:
        return None, resultado, warnings

    lienzo = Lienzo(modelo=model)
    lienzo.visual_layout = {
        "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
        "nodes": positions,
        "links": {},
    }
    saved = await service.repository.guardar(lienzo=lienzo, owner_id=owner_id)
    return saved, resultado, warnings
