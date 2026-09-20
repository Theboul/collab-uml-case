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
from typing import Any

import pytest
from jsonschema import ValidationError

from backend_case.app.modeling.application.canvas_delta import (
    MODEL_KINDS,
    canvas_state,
    compute_delta,
)
from backend_case.app.modeling.application.commands.dispatcher import CommandDispatcher
from backend_case.app.schemas.canvas import to_detail_schema
from backend_case.tests.canvas_delta_contract import (
    SCHEMA_FILE,
    schema_validator,
    validate_canvas_delta_message,
)
from backend_case.tests.canvas_delta_scenarios import (
    CLIENTE,
    PEDIDO,
    STEPS,
    empty_lienzo,
    run_scenario,
)

EXAMPLES_FILE = SCHEMA_FILE.with_name("canvas-delta.examples.json")


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
        validate_canvas_delta_message(paso["message"])
        estado = apply_delta(estado, paso["message"]["delta"])
        assert estado == paso["after"], paso["name"]


def test_el_esquema_lista_las_mismas_clases_de_elemento_que_el_codigo():
    esquema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))

    model = esquema["$defs"]["CanvasDelta"]["properties"]["model"]["properties"]

    assert tuple(model) == MODEL_KINDS
    assert esquema["properties"]["type"] == {"const": "canvas_delta"}


def _mensaje(**cambios: Any) -> dict[str, Any]:
    return {"type": "canvas_delta", "fromVersion": 1, "toVersion": 2, "delta": {}, **cambios}


MENSAJES_QUE_NO_CUMPLEN = {
    "vacío": {},
    "el canvas_update que ya no existe": {"type": "canvas_update", "canvas": {}},
    "sin delta": {"type": "canvas_delta", "fromVersion": 1, "toVersion": 2},
    "sin fromVersion": {"type": "canvas_delta", "toVersion": 2, "delta": {}},
    "un campo de más": _mensaje(canvas={}),
    "fromVersion como texto": _mensaje(fromVersion="1"),
    "fromVersion 0": _mensaje(fromVersion=0, toVersion=1),
    "las versiones no son consecutivas": _mensaje(fromVersion=1, toVersion=3),
    "delta que no es un objeto": _mensaje(delta=[]),
    "tipo de elemento desconocido": _mensaje(delta={"model": {"interfaces": {"remove": ["x"]}}}),
    "cambio de elementos vacío": _mensaje(delta={"model": {"classes": {}}}),
    "upsert vacío": _mensaje(delta={"model": {"classes": {"upsert": []}}}),
    "upsert sin id": _mensaje(delta={"model": {"classes": {"upsert": [{"name": "A"}]}}}),
    "remove con un id que no es texto": _mensaje(delta={"model": {"classes": {"remove": [1]}}}),
    "clave de más en un cambio": _mensaje(delta={"model": {"classes": {"replace": ["a"]}}}),
    "sección de layout desconocida": _mensaje(delta={"layout": {"grid": {}}}),
    "cambio de layout vacío": _mensaje(delta={"layout": {"nodes": {}}}),
    "clave de más en el delta": _mensaje(delta={"extras": {}}),
}


@pytest.mark.parametrize("malo", MENSAJES_QUE_NO_CUMPLEN.values(), ids=MENSAJES_QUE_NO_CUMPLEN)
def test_el_contrato_rechaza_mensajes_que_no_cumplen(malo):
    with pytest.raises(ValidationError):
        validate_canvas_delta_message(malo)


def test_el_esquema_por_si_solo_exige_versiones_positivas():
    """Un consumidor que solo use el JSON Schema (sin la regla de versiones consecutivas) sigue
    rechazando versiones que no existen."""
    assert not schema_validator().is_valid(_mensaje(fromVersion=0, toVersion=2))
    assert not schema_validator().is_valid(_mensaje(fromVersion=1, toVersion=1))
    assert schema_validator().is_valid(_mensaje(fromVersion=1, toVersion=2))


def test_el_contrato_acepta_el_delta_vacio_y_el_viewport_nulo():
    validate_canvas_delta_message(_mensaje())
    validate_canvas_delta_message(_mensaje(delta={"layout": {"viewport": None}}))
