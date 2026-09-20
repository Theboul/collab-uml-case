"""
Delta de un Lienzo (`canvas_delta`): la propiedad central es `aplicar(delta, antes) == después`
sobre comandos REALES del despachador. También cubre la mínima expresión del delta, la
independencia del estado capturado y el contrato compartido con el frontend
(`contracts/canvas-delta.v1.json` y sus ejemplos, que se generan desde aquí y consume el spec
de TypeScript).
"""

import copy
import json
import os
from pathlib import Path
from typing import Any

import pytest

from backend_case.app.modeling.application.canvas_delta import (
    MODEL_KINDS,
    canvas_state,
    compute_delta,
)
from backend_case.app.modeling.application.commands.dispatcher import CommandDispatcher
from backend_case.app.schemas.canvas import to_detail_schema
from backend_case.tests.canvas_delta_scenarios import (
    CLIENTE,
    PEDIDO,
    STEPS,
    empty_lienzo,
    run_scenario,
)

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
SCHEMA_FILE = CONTRACTS / "canvas-delta.v1.json"
EXAMPLES_FILE = CONTRACTS / "canvas-delta.examples.json"


def apply_delta(state: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Aplicador de referencia (lo que debe hacer cualquier cliente)."""
    result = copy.deepcopy(state)
    for kind, change in delta.get("model", {}).items():
        removed = set(change.get("remove", []))
        items = [e for e in result["model"][kind] if e["id"] not in removed]
        position = {e["id"]: i for i, e in enumerate(items)}
        for element in change.get("upsert", []):
            if element["id"] in position:
                items[position[element["id"]]] = element
            else:
                items.append(element)
        result["model"][kind] = items
    layout = delta.get("layout", {})
    for section in ("nodes", "links"):
        change = layout.get(section)
        if change:
            target = result["layout"].setdefault(section, {})
            for key in change.get("remove", []):
                target.pop(key, None)
            target.update(change.get("set", {}))
    if "viewport" in layout:
        result["layout"]["viewport"] = layout["viewport"]
    return result


# --------------------------------------------------------------------------------------------
# La propiedad central
# --------------------------------------------------------------------------------------------


def test_aplicar_el_delta_al_estado_anterior_da_el_estado_posterior_en_cada_comando():
    initial, steps = run_scenario()
    estado = initial

    for step in steps:
        estado = apply_delta(estado, step["delta"])
        assert estado == step["after"], f"falla tras: {step['name']}"


def test_el_escenario_cubre_todos_los_tipos_de_comando_que_afectan_al_modelo_o_al_layout():
    comandos = {command for _, command, _ in STEPS}
    assert {
        "CREATE_CLASS",
        "UPDATE_CLASS_NAME",
        "DELETE_ELEMENTS",
        "ADD_ATTRIBUTE",
        "UPDATE_ATTRIBUTE",
        "DELETE_ATTRIBUTE",
        "ADD_OPERATION",
        "ADD_PARAMETER",
        "CREATE_RELATION",
        "DELETE_RELATION",
        "MOVE_ELEMENT",
        "RESIZE_ELEMENT",
        "UPDATE_RELATION_VERTICES",
        "UPDATE_VIEWPORT",
    } <= comandos


# --------------------------------------------------------------------------------------------
# El delta es mínimo: solo viaja lo que cambió
# --------------------------------------------------------------------------------------------


def _paso(nombre: str) -> dict[str, Any]:
    _, steps = run_scenario()
    return next(s for s in steps if s["name"] == nombre)


def test_mover_una_clase_solo_cambia_el_layout_de_ese_nodo():
    delta = _paso("mover una clase")["delta"]

    assert set(delta) == {"layout"}
    assert set(delta["layout"]) == {"nodes"}
    assert set(delta["layout"]["nodes"]["set"]) == {PEDIDO}
    assert "remove" not in delta["layout"]["nodes"]


def test_agregar_un_atributo_reenvia_solo_esa_clase_y_no_toca_el_layout():
    delta = _paso("agregar un atributo")["delta"]

    assert set(delta) == {"model"}
    assert set(delta["model"]) == {"classes"}
    assert [c["id"] for c in delta["model"]["classes"]["upsert"]] == [CLIENTE]


def test_borrar_una_clase_arrastra_sus_relaciones_y_su_posicion():
    delta = _paso("borrar una clase con sus relaciones")["delta"]

    assert delta["model"]["classes"] == {"remove": [PEDIDO]}
    assert delta["model"]["generalizations"] == {"remove": ["r-fp"]}
    assert delta["layout"]["nodes"] == {"remove": [PEDIDO]}


def test_crear_una_generalizacion_solo_toca_esa_lista():
    delta = _paso("crear una generalización")["delta"]

    assert set(delta["model"]) == {"generalizations"}
    assert "layout" not in delta


def test_crear_una_dependencia_solo_toca_esa_lista():
    delta = _paso("crear una dependencia")["delta"]

    assert set(delta["model"]) == {"dependencies"}
    assert [d["id"] for d in delta["model"]["dependencies"]["upsert"]] == ["r-cf"]
    assert "layout" not in delta


def test_sin_cambios_el_delta_es_vacio():
    lienzo = empty_lienzo()
    estado = canvas_state(lienzo)

    assert compute_delta(estado, canvas_state(lienzo)) == {}


def test_un_comando_sin_efecto_produce_un_delta_vacio():
    lienzo = empty_lienzo()
    despachador = CommandDispatcher()
    despachador.dispatch(
        lienzo, "CREATE_CLASS", {"classId": CLIENTE, "name": "Cliente", "x": 1, "y": 2}
    )
    antes = canvas_state(lienzo)

    despachador.dispatch(
        lienzo, "MOVE_ELEMENT", {"elementId": CLIENTE, "x": 1, "y": 2}
    )  # misma posición

    assert compute_delta(antes, canvas_state(lienzo)) == {}


# --------------------------------------------------------------------------------------------
# El estado capturado es independiente y compatible con el HTTP
# --------------------------------------------------------------------------------------------


def test_el_estado_capturado_antes_no_cambia_cuando_un_comando_muta_el_layout_en_sitio():
    """Regresión del alias: si el layout se compartiera, antes y después serían iguales."""
    lienzo = empty_lienzo()
    despachador = CommandDispatcher()
    despachador.dispatch(
        lienzo, "CREATE_CLASS", {"classId": CLIENTE, "name": "Cliente", "x": 1, "y": 2}
    )
    antes = canvas_state(lienzo)
    antes_copia = copy.deepcopy(antes)

    despachador.dispatch(lienzo, "MOVE_ELEMENT", {"elementId": CLIENTE, "x": 50, "y": 60})

    assert antes == antes_copia
    assert (
        compute_delta(antes, canvas_state(lienzo))["layout"]["nodes"]["set"][CLIENTE]["x"] == 50.0
    )


def test_compute_delta_no_muta_sus_argumentos():
    initial, steps = run_scenario()
    antes = copy.deepcopy(initial)
    despues = copy.deepcopy(steps[-1]["after"])

    compute_delta(antes, despues)

    assert antes == initial and despues == steps[-1]["after"]


def test_el_estado_tiene_la_misma_forma_que_el_lienzo_que_devuelve_http():
    lienzo = empty_lienzo()
    CommandDispatcher().dispatch(
        lienzo, "CREATE_CLASS", {"classId": CLIENTE, "name": "Cliente", "x": 1, "y": 2}
    )

    http = to_detail_schema(lienzo, 2).model_dump(mode="json")

    estado = canvas_state(lienzo)
    assert estado["model"] == {kind: http["model"][kind] for kind in MODEL_KINDS}
    assert estado["layout"] == http["visualLayout"]


def test_todos_los_deltas_son_serializables_a_json():
    _, steps = run_scenario()

    for step in steps:
        assert json.loads(json.dumps(step["delta"])) == step["delta"]


# --------------------------------------------------------------------------------------------
# Contrato compartido con el frontend
# --------------------------------------------------------------------------------------------


def validate_message(message: dict[str, Any]) -> None:
    """Comprobación estructural equivalente a `contracts/canvas-delta.v1.json` (sin librerías)."""
    assert set(message) == {"type", "fromVersion", "toVersion", "delta"}
    assert message["type"] == "canvas_delta"
    assert isinstance(message["fromVersion"], int) and message["fromVersion"] >= 1
    assert message["toVersion"] == message["fromVersion"] + 1
    delta = message["delta"]
    assert set(delta) <= {"model", "layout"}
    for kind, change in delta.get("model", {}).items():
        assert kind in MODEL_KINDS
        assert change and set(change) <= {"upsert", "remove"}
        assert all(isinstance(e["id"], str) for e in change.get("upsert", []))
        assert all(isinstance(i, str) for i in change.get("remove", []))
    layout = delta.get("layout", {})
    assert set(layout) <= {"nodes", "links", "viewport"}
    for section in ("nodes", "links"):
        if section in layout:
            assert layout[section] and set(layout[section]) <= {"set", "remove"}
    assert layout.get("viewport", {}) is None or isinstance(layout.get("viewport", {}), dict)


def _examples_document() -> dict[str, Any]:
    initial, steps = run_scenario()
    return {
        "description": "Generado por backend_case/tests/test_canvas_delta.py con comandos reales "
        "del despachador. `initial` es el estado de partida; cada paso trae el mensaje "
        "`canvas_delta` "
        "completo y el estado resultante (`after`). Regenerar: UPDATE_CONTRACTS=1 pytest "
        "backend_case/tests/test_canvas_delta.py",
        "initial": initial,
        "steps": [
            {
                "name": step["name"],
                "command": step["command"],
                "message": {
                    "type": "canvas_delta",
                    "fromVersion": index + 1,
                    "toVersion": index + 2,
                    "delta": step["delta"],
                },
                "after": step["after"],
            }
            for index, step in enumerate(steps)
        ],
    }


def test_los_ejemplos_del_contrato_estan_al_dia():
    """Si cambia el delta, los ejemplos (que consume el frontend) deben regenerarse y revisarse."""
    generado = _examples_document()
    if os.environ.get("UPDATE_CONTRACTS") == "1":
        EXAMPLES_FILE.write_text(
            json.dumps(generado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    assert EXAMPLES_FILE.exists(), "faltan los ejemplos: UPDATE_CONTRACTS=1 pytest ..."
    assert json.loads(EXAMPLES_FILE.read_text(encoding="utf-8")) == generado


def test_cada_mensaje_de_ejemplo_cumple_el_contrato_y_encadena_con_el_siguiente():
    documento = json.loads(EXAMPLES_FILE.read_text(encoding="utf-8"))
    estado = documento["initial"]

    for paso in documento["steps"]:
        validate_message(paso["message"])
        estado = apply_delta(estado, paso["message"]["delta"])
        assert estado == paso["after"], paso["name"]


def test_el_esquema_lista_las_mismas_clases_de_elemento_que_el_codigo():
    esquema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

    model = esquema["$defs"]["CanvasDelta"]["properties"]["model"]["properties"]

    assert tuple(model) == MODEL_KINDS
    assert esquema["properties"]["type"] == {"const": "canvas_delta"}


@pytest.mark.parametrize(
    "malo", [{}, {"type": "canvas_update"}, {"type": "canvas_delta", "fromVersion": 1}]
)
def test_el_validador_rechaza_mensajes_que_no_cumplen(malo):
    with pytest.raises(AssertionError):
        validate_message(malo)
