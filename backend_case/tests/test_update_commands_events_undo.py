"""
UPDATE_CLASS_NAME / UPDATE_ATTRIBUTE / UPDATE_OPERATION delegan en el dominio (`editar_*`):

- `undoPayload` lleva el valor ANTERIOR de lo que cambió, con la convención de DELETE_ELEMENTS
  (payload del comando inverso; el tipo lo deduce el cliente). Aplicarlo restaura el modelo.
- una edición que no cambia nada no genera undo.
- el evento de dominio se registra (log) DESPUÉS de persistir, y solo si se persistió.
"""

import logging

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app

SERVICE_LOGGER = "backend_case.app.modeling.application.canvas_service"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


class _Canvas:
    """Lienzo con la clase c-1 (Factura), el atributo a-1 y la operación o-1."""

    def __init__(self, client: TestClient) -> None:
        self.client = client
        res = client.post("/api/v2/canvases", json={"name": "Lienzo undo"})
        assert res.status_code == 201
        self.id, self.version = res.json()["id"], res.json()["version"]
        self.send("CREATE_CLASS", {"classId": "c-1", "name": "Factura"})
        self.send(
            "ADD_ATTRIBUTE",
            {
                "classId": "c-1",
                "attributeId": "a-1",
                "name": "numero",
                "type": "String",
                "visibility": "-",
            },
        )
        self.send(
            "ADD_OPERATION", {"classId": "c-1", "id": "o-1", "name": "emitir", "returnType": "void"}
        )

    def raw(self, cmd_type: str, payload: dict, version: int | None = None):
        return self.client.post(
            f"/api/v2/canvases/{self.id}/commands",
            json={
                "expectedVersion": self.version if version is None else version,
                "type": cmd_type,
                "payload": payload,
            },
        )

    def send(self, cmd_type: str, payload: dict) -> dict:
        res = self.raw(cmd_type, payload)
        assert res.status_code == 200, res.text
        self.version = res.json()["version"]
        return res.json()

    def clase(self, body: dict) -> dict:
        return next(c for c in body["canvas"]["model"]["classes"] if c["id"] == "c-1")


@pytest.fixture
def canvas(client) -> _Canvas:
    return _Canvas(client)


def test_update_attribute_devuelve_undo_con_el_valor_anterior_y_aplicarlo_restaura(canvas):
    body = canvas.send(
        "UPDATE_ATTRIBUTE",
        {
            "classId": "c-1",
            "attributeId": "a-1",
            "name": "codigo",
            "visibility": "+",
            "type": "String",
        },
    )

    # `type` no cambió: no aparece. `visibility` viaja como su valor ("-"), no como el Enum.
    assert body["undoPayload"] == {
        "classId": "c-1",
        "attributeId": "a-1",
        "name": "numero",
        "visibility": "-",
    }

    restored = canvas.send("UPDATE_ATTRIBUTE", body["undoPayload"])
    attr = canvas.clase(restored)["attributes"][0]
    assert (attr["name"], attr["visibility"]) == ("numero", "-")


def test_update_operation_devuelve_undo_con_el_valor_anterior_y_aplicarlo_restaura(canvas):
    body = canvas.send(
        "UPDATE_OPERATION",
        {
            "classId": "c-1",
            "operationId": "o-1",
            "name": "anular",
            "returnType": "bool",
            "isStatic": True,
        },
    )

    assert body["undoPayload"] == {
        "classId": "c-1",
        "operationId": "o-1",
        "name": "emitir",
        "returnType": "void",
        "isStatic": False,
    }

    restored = canvas.send("UPDATE_OPERATION", body["undoPayload"])
    op = canvas.clase(restored)["operations"][0]
    assert (op["name"], op["returnType"], op["isStatic"]) == ("emitir", "void", False)


def test_update_class_devuelve_undo_con_nombre_y_abstraccion_anteriores(canvas):
    body = canvas.send(
        "UPDATE_CLASS_NAME", {"classId": "c-1", "name": "Boleta", "isAbstract": True}
    )

    assert body["undoPayload"] == {"classId": "c-1", "name": "Factura", "isAbstract": False}

    restored = canvas.send("UPDATE_CLASS_NAME", body["undoPayload"])
    assert (canvas.clase(restored)["name"], canvas.clase(restored)["isAbstract"]) == (
        "Factura",
        False,
    )


def test_update_class_alternar_abstraccion_reenviando_el_nombre_lleva_el_nombre_actual_en_el_undo(
    canvas,
):
    # Así lo manda el frontend al marcar "abstracta": reenvía el mismo nombre.
    body = canvas.send(
        "UPDATE_CLASS_NAME", {"classId": "c-1", "name": "Factura", "isAbstract": True}
    )

    assert body["undoPayload"] == {"classId": "c-1", "name": "Factura", "isAbstract": False}


@pytest.mark.parametrize(
    ("cmd_type", "payload"),
    [
        ("UPDATE_CLASS_NAME", {"classId": "c-1", "name": "Factura"}),
        (
            "UPDATE_ATTRIBUTE",
            {"classId": "c-1", "attributeId": "a-1", "name": "numero", "type": "String"},
        ),
        (
            "UPDATE_OPERATION",
            {"classId": "c-1", "operationId": "o-1", "name": "emitir", "isStatic": False},
        ),
    ],
)
def test_una_edicion_que_no_cambia_nada_no_genera_undo(canvas, cmd_type, payload):
    body = canvas.send(cmd_type, payload)

    assert body["undoPayload"] is None


def test_el_evento_de_dominio_se_registra_tras_persistir(canvas, caplog):
    caplog.set_level(logging.INFO, logger=SERVICE_LOGGER)

    canvas.send("UPDATE_ATTRIBUTE", {"classId": "c-1", "attributeId": "a-1", "name": "codigo"})

    registros = [r.getMessage() for r in caplog.records if r.name == SERVICE_LOGGER]
    assert any("ElementoModificado" in m and "a-1" in m and "codigo" in m for m in registros), (
        registros
    )


def test_un_guardado_rechazado_por_conflicto_de_version_no_registra_el_evento(canvas, caplog):
    stale_version = canvas.version
    canvas.send("UPDATE_ATTRIBUTE", {"classId": "c-1", "attributeId": "a-1", "name": "codigo"})
    caplog.clear()
    caplog.set_level(logging.INFO, logger=SERVICE_LOGGER)

    res = canvas.raw(
        "UPDATE_ATTRIBUTE",
        {"classId": "c-1", "attributeId": "a-1", "name": "otro"},
        version=stale_version,
    )

    assert res.status_code == 409
    assert not [
        r
        for r in caplog.records
        if r.name == SERVICE_LOGGER and "ElementoModificado" in r.getMessage()
    ]


def test_las_violaciones_de_unicidad_siguen_devolviendo_el_mismo_error_de_api(canvas):
    canvas.send(
        "ADD_ATTRIBUTE", {"classId": "c-1", "attributeId": "a-2", "name": "total", "type": "Double"}
    )

    res = canvas.raw("UPDATE_ATTRIBUTE", {"classId": "c-1", "attributeId": "a-1", "name": "TOTAL"})

    assert res.status_code == 422
    assert res.json()["code"] == "UML_INVALID_MODEL"
    assert "Ya existe otro atributo llamado 'TOTAL'" in res.json()["message"]
