"""
Validación de mensajes `canvas_delta` contra el contrato real, `contracts/canvas-delta.v1.json`,
con `jsonschema` (Draft 2020-12). Lo usan los tests del delta y los del canal WebSocket.
"""

import json
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

SCHEMA_FILE = Path(__file__).resolve().parents[2] / "contracts" / "canvas-delta.v1.json"


@cache
def schema_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)  # el propio contrato debe ser un esquema válido
    return Draft202012Validator(schema)


def validate_canvas_delta_message(message: Any) -> None:
    """Lanza `jsonschema.ValidationError` si el mensaje no cumple el contrato."""
    schema_validator().validate(message)
    # Lo único que JSON Schema no puede expresar: cada guardado sube la versión en uno.
    if message["toVersion"] != message["fromVersion"] + 1:
        raise ValidationError("toVersion debe ser fromVersion + 1")
