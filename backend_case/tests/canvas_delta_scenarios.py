"""
Escenario compartido de los tests del delta: una secuencia de comandos REALES del despachador que
cubre cada tipo de cambio. Lo usan la propiedad `aplicar(delta, antes) == después` y la generación
de los ejemplos del contrato (`contracts/canvas-delta.examples.json`), que el frontend consume.
Los ids son fijos para que el resultado sea determinista.
"""

import copy
from typing import Any

from backend_case.app.modeling.application.canvas_delta import (
    CanvasDelta,
    CanvasState,
    canvas_state,
    compute_delta,
)
from backend_case.app.modeling.application.commands.dispatcher import CommandDispatcher
from core.uml_domain.model import Lienzo

CLIENTE, PEDIDO, FACTURA = "c-cliente", "c-pedido", "c-factura"

STEPS: list[tuple[str, str, dict[str, Any]]] = [
    (
        "crear la clase Cliente",
        "CREATE_CLASS",
        {"classId": CLIENTE, "name": "Cliente", "x": 100, "y": 80},
    ),
    (
        "crear la clase Pedido",
        "CREATE_CLASS",
        {"classId": PEDIDO, "name": "Pedido", "x": 400, "y": 80},
    ),
    (
        "agregar un atributo",
        "ADD_ATTRIBUTE",
        {"classId": CLIENTE, "id": "a-nombre", "name": "nombre", "type": "String"},
    ),
    (
        "renombrar el atributo",
        "UPDATE_ATTRIBUTE",
        {"classId": CLIENTE, "attributeId": "a-nombre", "name": "nombreCompleto"},
    ),
    (
        "agregar una operación",
        "ADD_OPERATION",
        {"classId": PEDIDO, "id": "o-total", "name": "total", "returnType": "float"},
    ),
    (
        "agregar un parámetro",
        "ADD_PARAMETER",
        {
            "classId": PEDIDO,
            "operationId": "o-total",
            "id": "p-iva",
            "name": "iva",
            "type": "float",
        },
    ),
    (
        "crear una asociación",
        "CREATE_RELATION",
        {
            "relationId": "r-cp",
            "type": "ASSOCIATION",
            "sourceClassId": CLIENTE,
            "targetClassId": PEDIDO,
            "sourceMultiplicity": "1",
            "targetMultiplicity": "0..*",
            "name": "realiza",
        },
    ),
    (
        "crear la clase Factura",
        "CREATE_CLASS",
        {"classId": FACTURA, "name": "Factura", "x": 400, "y": 300},
    ),
    (
        "crear una generalización",
        "CREATE_RELATION",
        {
            "relationId": "r-fp",
            "type": "GENERALIZATION",
            "sourceClassId": FACTURA,
            "targetClassId": PEDIDO,
        },
    ),
    (
        "crear una dependencia",
        "CREATE_RELATION",
        {
            "relationId": "r-cf",
            "type": "DEPENDENCY",
            "sourceClassId": CLIENTE,
            "targetClassId": FACTURA,
        },
    ),
    ("renombrar una clase", "UPDATE_CLASS_NAME", {"classId": CLIENTE, "name": "Persona"}),
    ("mover una clase", "MOVE_ELEMENT", {"elementId": PEDIDO, "x": 420, "y": 95}),
    (
        "redimensionar una clase",
        "RESIZE_ELEMENT",
        {"elementId": PEDIDO, "width": 260, "height": 170},
    ),
    (
        "cambiar los vértices de una relación",
        "UPDATE_RELATION_VERTICES",
        {"relationId": "r-cp", "vertices": [{"x": 300, "y": 200}]},
    ),
    ("mover el viewport", "UPDATE_VIEWPORT", {"zoom": 1.5, "panX": 40, "panY": -10}),
    ("borrar un atributo", "DELETE_ATTRIBUTE", {"classId": CLIENTE, "attributeId": "a-nombre"}),
    ("borrar una relación", "DELETE_RELATION", {"relationId": "r-cp"}),
    ("borrar una clase con sus relaciones", "DELETE_ELEMENTS", {"classIds": [PEDIDO]}),
]


def empty_lienzo() -> Lienzo:
    lienzo, _ = Lienzo.crear_nuevo()
    lienzo.visual_layout = {
        "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
        "nodes": {},
        "links": {},
    }
    return lienzo


def run_scenario() -> tuple[CanvasState, list[dict[str, Any]]]:
    """Estado inicial y, por comando, el delta y el estado resultante (copias independientes)."""
    lienzo = empty_lienzo()
    dispatcher = CommandDispatcher()
    initial = canvas_state(lienzo)
    before = initial
    steps: list[dict[str, Any]] = []
    for name, command, payload in STEPS:
        dispatcher.dispatch(lienzo, command, payload)
        after = canvas_state(lienzo)
        delta: CanvasDelta = compute_delta(before, after)
        steps.append(
            {"name": name, "command": command, "delta": delta, "after": copy.deepcopy(after)}
        )
        before = after
    return initial, steps
