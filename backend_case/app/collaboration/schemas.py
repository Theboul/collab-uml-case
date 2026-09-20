"""
Contrato de los mensajes que una Sesión puede enviar por el canal de colaboración (ADR-0003).
Todo lo demás se rechaza: solo el servidor emite `canvas_update`.

Dos clases de rechazo, con distinto castigo:
- `InvalidClientMessageError`: violación de protocolo (demasiado grande, no es JSON, tipo no
  permitido). El router cierra la conexión.
- `InvalidMessageFieldsError`: un tipo permitido con campos inválidos (p. ej. una coordenada
  `null`, que es lo que produce `JSON.stringify(NaN)`). Cursor y arrastre son flujos con pérdida:
  se descarta el mensaje sin cerrar, igual que el exceso de frecuencia.
"""

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

MAX_MESSAGE_BYTES = 4096

Coordinate = Annotated[float, Field(allow_inf_nan=False)]
NodeId = Annotated[str, Field(min_length=1, max_length=128)]


class InvalidClientMessageError(ValueError):
    """Violación de protocolo: mensaje demasiado grande, que no es JSON o de tipo no permitido."""


class InvalidMessageFieldsError(ValueError):
    """Tipo de mensaje permitido, pero con campos ausentes o inválidos."""


class CursorMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["cursor"]
    x: Coordinate
    y: Coordinate


class NodeDragMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["node_drag"]
    nodeId: NodeId
    x: Coordinate
    y: Coordinate


class NodeDragEndMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: Literal["node_drag_end"]
    nodeId: NodeId


_MESSAGE_MODELS: dict[str, type[BaseModel]] = {
    "cursor": CursorMessage,
    "node_drag": NodeDragMessage,
    "node_drag_end": NodeDragEndMessage,
}


def parse_client_message(text: str) -> dict[str, Any]:
    """Valida el texto y devuelve solo los campos del contrato (descarta los extra)."""
    if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise InvalidClientMessageError("mensaje demasiado grande")
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as err:  # RecursionError: anidamiento extremo en <4 KB
        raise InvalidClientMessageError("el mensaje no es JSON") from err

    message_type = data.get("type") if isinstance(data, dict) else None
    model = _MESSAGE_MODELS.get(message_type) if isinstance(message_type, str) else None
    if model is None:
        raise InvalidClientMessageError("tipo de mensaje no permitido")
    try:
        return model.model_validate(data).model_dump()
    except ValidationError as err:
        raise InvalidMessageFieldsError("campos inválidos") from err
