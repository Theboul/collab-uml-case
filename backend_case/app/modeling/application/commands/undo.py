"""
Payload de undo para comandos de edición (UPDATE_*).

Sigue la convención de `undoPayload` que ya usan DELETE_ELEMENTS/CREATE_CLASS: es el *payload* del
comando inverso, y el tipo del comando inverso lo deduce el cliente (para un UPDATE_* es el mismo
UPDATE_*). Se arma desde el evento de dominio, que ya trae el valor anterior de cada campo.
"""

from enum import Enum
from typing import Any

from core.uml_domain.events import ElementoModificado


def inverso_de_edicion(
    evento: ElementoModificado, claves: dict[str, str], base: dict[str, Any]
) -> dict[str, Any]:
    """
    `base` lleva los ids del comando; `claves` traduce el campo de dominio (snake_case) a la clave
    del comando (camelCase). Cada campo que cambió vuelve a su valor ANTERIOR.
    """
    inverso = dict(base)
    for cambio in evento.cambios:
        anterior = cambio.anterior
        inverso[claves[cambio.campo]] = anterior.value if isinstance(anterior, Enum) else anterior
    return inverso
