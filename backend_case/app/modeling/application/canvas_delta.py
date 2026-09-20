"""
Diferencia entre dos estados de un Lienzo, para difundir solo lo que cambió (ADR-0003, Addendum).

El estado comparable tiene la misma forma que viaja por el cable (`UmlModelSchema` + layout), y el
delta es por elemento: una clase o relación que cambió viaja completa (`upsert`) y una que
desapareció viaja como id (`remove`). Es una diferencia entre el antes y el después de un
comando, así que no depende de qué comando la produjo ni toca `core/uml_domain`. Contrato:
`contracts/canvas-delta.v1.json`.
"""

import copy
from typing import Any

from backend_case.app.application.mappers import DomainToPydanticMapper
from core.uml_domain.model import Lienzo

MODEL_KINDS = ("classes", "associations", "generalizations", "realizations", "dependencies")

CanvasState = dict[str, Any]
CanvasDelta = dict[str, Any]


def canvas_state(lienzo: Lienzo) -> CanvasState:
    """
    Estado comparable de un Lienzo. Es una copia: el layout se copia en profundidad porque los
    comandos lo mutan en sitio, y un estado capturado "antes" que compartiera esos diccionarios
    quedaría igual al de "después" y ocultaría los cambios.
    """
    model = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo).model_dump(mode="json")
    layout = lienzo.visual_layout
    return {
        "model": {kind: model[kind] for kind in MODEL_KINDS},
        "layout": copy.deepcopy(layout) if isinstance(layout, dict) else {},
    }


def compute_delta(before: CanvasState, after: CanvasState) -> CanvasDelta:
    """Lo mínimo que hay que aplicar a `before` para obtener `after`. `{}` si no cambió nada."""
    model = {
        kind: change
        for kind in MODEL_KINDS
        if (change := _diff_by_id(before["model"][kind], after["model"][kind]))
    }
    layout = _diff_layout(before["layout"], after["layout"])
    return {**({"model": model} if model else {}), **({"layout": layout} if layout else {})}


def _diff_by_id(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> dict[str, list[Any]]:
    old_by_id = {element["id"]: element for element in old}
    new_ids = {element["id"] for element in new}
    upsert = [element for element in new if old_by_id.get(element["id"]) != element]
    remove = [element_id for element_id in old_by_id if element_id not in new_ids]
    return {**({"upsert": upsert} if upsert else {}), **({"remove": remove} if remove else {})}


def _diff_layout(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for section in ("nodes", "links"):
        old_items: dict[str, Any] = old.get(section) or {}
        new_items: dict[str, Any] = new.get(section) or {}
        changed = {key: value for key, value in new_items.items() if old_items.get(key) != value}
        removed = [key for key in old_items if key not in new_items]
        if changed or removed:
            result[section] = {
                **({"set": changed} if changed else {}),
                **({"remove": removed} if removed else {}),
            }
    if old.get("viewport") != new.get("viewport"):
        result["viewport"] = new.get("viewport")
    return result
