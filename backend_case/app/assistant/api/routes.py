"""
Rutas API para CU6 (texto/voz) y CU7 (imagen): generar/ampliar/editar el
modelo UML por IA, aplicado siempre a través del pipeline de comandos ya
validado de modeling (CommandDispatcher + core/uml_domain) en vez de aplicar
la respuesta cruda de la IA directo al modelo persistido.

CU6 -- dos formas de respuesta de Gemini, resueltas por gemini_command_mapper:
- Creación desde cero ({"classes": [...], "relationships": [...]}).
- Operaciones sobre el modelo existente ({"operations": [...]}), identificadas
  por nombre -- por eso acá se carga el lienzo actual ANTES de llamar a
  Gemini, para poder darle el modelo real como contexto del prompt.

CU7 -- reutiliza call_gemini_from_image tal cual (legacy/services_gemini.py):
ya devuelve la respuesta post-procesada en la MISMA forma de creación que usa
CU6 texto ({"classes": [...], "relationships": [...]}), así que se la pasa
directo al mismo map_gemini_response_to_commands -- sin mapper nuevo.
"""

import base64
import json
import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.assistant.application.gemini_command_mapper import (
    build_model_context,
    map_gemini_response_to_commands,
    resolve_operation,
    validate_operations_shape,
)
from backend_case.app.legacy.services_gemini import call_gemini, call_gemini_from_image
from backend_case.app.modeling.api.routes import CommandResponse
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasResult
from backend_case.app.schemas.canvas import CanvasDetailSchema, to_detail_schema
from backend_case.app.shared.deps import get_canvas_service
from core.uml_domain.exceptions import UmlValidationError

from ...shared.security.dependencies import get_current_user_optional
from ...shared.security.models import UserORM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/canvases", tags=["assistant"])

CanvasServiceDep = Annotated[CanvasService, Depends(get_canvas_service)]
CurrentUserOptionalDep = Annotated[UserORM | None, Depends(get_current_user_optional)]


class TextCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    prompt: str = Field(..., min_length=1)
    expectedVersion: int


def _strip_markdown_fences(text: str) -> str:
    return re.sub(r"^```json\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


def _build_command_response(result: CanvasResult) -> CommandResponse:
    canvas_schema: CanvasDetailSchema = to_detail_schema(
        result.lienzo, result.version, result.owner_id, result.room_name
    )
    return CommandResponse(
        accepted=True,
        version=result.version,
        canvas=canvas_schema,
    )


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

    return _build_command_response(result)


@router.post("/{canvas_id}/assistant/image-command", response_model=CommandResponse)
async def execute_image_command(
    canvas_id: str,
    service: CanvasServiceDep,
    image: Annotated[UploadFile, File()],
    expected_version: Annotated[int, Form(alias="expectedVersion")],
    current_user: CurrentUserOptionalDep = None,
) -> CommandResponse:
    """
    CU7: interpreta una imagen de un diagrama de clases (dibujado a mano,
    capturado o exportado) y la traduce a comandos reales de creación --
    mismo pipeline que CU6 texto (CREATE_CLASS/ADD_ATTRIBUTE/ADD_OPERATION/
    CREATE_RELATION), validados por UMLValidator vía el dispatcher, aplicados
    de forma atómica sobre el lienzo persistido. Si la imagen es ilegible o
    Gemini no puede interpretarla, se rechaza con 422 explícito y el modelo
    persistido no cambia -- nunca se genera información inconsistente a
    partir de una detección fallida.
    """
    user_id = current_user.id if current_user else None

    content = await image.read()
    if not content:
        raise UmlValidationError("Debés subir un archivo de imagen.")

    image_base64 = base64.b64encode(content).decode("utf-8")
    mime_type = image.content_type or "image/png"

    image_result = call_gemini_from_image(image_base64, mime_type=mime_type)

    # call_gemini_from_image atrapa sus propias excepciones y devuelve
    # {"error": ...} en vez de propagar -- se chequea explícito acá. El detalle
    # real (image_result["error"]) NO se expone al cliente: es la excepción cruda
    # de requests, que para errores HTTP incluye la URL completa de la request
    # -- con la API key de Gemini en el query string (?key=...). Se loguea server-
    # side para diagnóstico y se devuelve un mensaje genérico, nunca la excepción
    # cruda de una llamada externa.
    if isinstance(image_result, dict) and "error" in image_result:
        logger.warning("call_gemini_from_image falló: %s", image_result["error"])
        raise UmlValidationError(
            "No se pudo interpretar la imagen del diagrama. Probá con una foto más "
            "clara o de mejor resolución."
        )

    # A diferencia del camino de texto, acá NO hay que parsear JSON ni sacar
    # fences de markdown: call_gemini_from_image ya devuelve un dict parseado
    # y post-procesado a la misma forma de creación que usa CU6 texto.
    commands = map_gemini_response_to_commands(image_result)

    result = await service.ejecutar_comandos_lote(
        canvas_id=canvas_id,
        expected_version=expected_version,
        commands=commands,
        user_id=user_id,
    )

    return _build_command_response(result)
