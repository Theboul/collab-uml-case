"""
Ruta API para CU6: generar/ampliar/editar el modelo UML por texto o voz
(dictado transcripto en el cliente vía Web Speech API, entra por este mismo
endpoint como texto). Reutiliza call_gemini tal cual (legacy/services_gemini.py)
y el pipeline de comandos ya validado de modeling (CommandDispatcher +
core/uml_domain) en vez de aplicar la respuesta de la IA directo al modelo
persistido.

Dos formas de respuesta de Gemini, resueltas por gemini_command_mapper:
- Creación desde cero ({"classes": [...], "relationships": [...]}).
- Operaciones sobre el modelo existente ({"operations": [...]}), identificadas
  por nombre -- por eso acá se carga el lienzo actual ANTES de llamar a
  Gemini, para poder darle el modelo real como contexto del prompt.
"""

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.assistant.application.gemini_command_mapper import (
    build_model_context,
    map_gemini_response_to_commands,
    resolve_operation,
    validate_operations_shape,
)
from backend_case.app.collaboration.room_registry import collaboration_room_registry
from backend_case.app.legacy.services_gemini import call_gemini
from backend_case.app.modeling.api.routes import (
    CanvasDetailSchema,
    CommandResponse,
    to_detail_schema,
)
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.shared.deps import get_canvas_service
from backend_case.app.shared.security.dependencies import get_current_user_optional
from backend_case.app.shared.security.models import UserORM
from core.uml_domain.exceptions import UmlValidationError

router = APIRouter(prefix="/canvases", tags=["assistant"])

CanvasServiceDep = Annotated[CanvasService, Depends(get_canvas_service)]
CurrentUserOptionalDep = Annotated[UserORM | None, Depends(get_current_user_optional)]


class TextCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(..., min_length=1)
    expectedVersion: int


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


@router.post("/{canvas_id}/assistant/text-command", response_model=CommandResponse)
async def execute_text_command(
    canvas_id: str,
    payload: TextCommandRequest,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
) -> CommandResponse:
    """
    CU6: interpreta una instrucción de texto/voz con Gemini y la traduce a
    comandos reales del editor -- creación (CREATE_CLASS/ADD_ATTRIBUTE/
    ADD_OPERATION/CREATE_RELATION) u operaciones de edición/eliminación sobre
    el modelo existente (UPDATE_CLASS_NAME/ADD_ATTRIBUTE/UPDATE_ATTRIBUTE/
    DELETE_ATTRIBUTE/ADD_OPERATION/DELETE_OPERATION/DELETE_ELEMENTS/
    CREATE_RELATION/DELETE_RELATION/UPDATE_RELATION/UPDATE_MULTIPLICITY),
    aplicados de forma atómica sobre el lienzo persistido. Si la IA devuelve
    algo que no mapea limpiamente (JSON roto, referencias inválidas, acción no
    soportada), se rechaza con 422 explícito y el modelo persistido no cambia.
    """
    user_id = current_user.id if current_user else None

    current = await service.obtener_lienzo(canvas_id, user_id=user_id)
    model_context = build_model_context(current.lienzo.modelo)

    raw_output = call_gemini(payload.prompt, model_context=model_context)
    cleaned = _strip_markdown_fences(raw_output) if isinstance(raw_output, str) else raw_output

    try:
        parsed: Any = json.loads(cleaned)
    except (TypeError, ValueError) as err:
        raise UmlValidationError("La IA no devolvió un JSON válido.") from err

    if isinstance(parsed, dict) and "operations" in parsed:
        operations = validate_operations_shape(parsed)
        result = await service.ejecutar_resolviendo_secuencial(
            canvas_id=canvas_id,
            expected_version=payload.expectedVersion,
            raw_items=operations,
            resolver=resolve_operation,
            user_id=user_id,
        )
    else:
        commands = map_gemini_response_to_commands(parsed)
        result = await service.ejecutar_comandos_lote(
            canvas_id=canvas_id,
            expected_version=payload.expectedVersion,
            commands=commands,
            user_id=user_id,
        )

    canvas_schema: CanvasDetailSchema = to_detail_schema(
        result.lienzo, result.version, result.owner_id, result.room_name
    )
    await collaboration_room_registry.broadcast(
        canvas_id,
        "",
        {"type": "canvas_update", "canvas": canvas_schema.model_dump(mode="json")},
    )
    return CommandResponse(
        accepted=True,
        version=result.version,
        canvas=canvas_schema,
    )
