"""
UPDATE_CLASS_NAME con `isAbstract`: el valor debe validarse/convertirse como booleano,
nunca evaluarse por truthiness (`bool("false")` es True en Python).

Regresión de un bug real: el handler leía `payload["isAbstract"]` crudo, fuera del esquema
del comando, así que un cliente que mandara el string "false" dejaba la clase abstracta.
"""

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app

CLASS_ID = "c-figura"


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _canvas_con_clase(client: TestClient, *, is_abstract: bool) -> tuple[str, int]:
    res = client.post("/api/v2/canvases", json={"name": "Lienzo isAbstract"})
    assert res.status_code == 201
    canvas_id, version = res.json()["id"], res.json()["version"]
    created = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"classId": CLASS_ID, "name": "Figura", "isAbstract": is_abstract},
        },
    )
    assert created.status_code == 200
    return canvas_id, created.json()["version"]


def _update_class(client: TestClient, canvas_id: str, version: int, **extra: object):
    return client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_CLASS_NAME",
            "payload": {"classId": CLASS_ID, "name": "Figura", **extra},
        },
    )


def _is_abstract(response) -> bool:
    classes = response.json()["canvas"]["model"]["classes"]
    return next(c for c in classes if c["id"] == CLASS_ID)["isAbstract"]


@pytest.mark.parametrize(
    ("raw", "esperado"),
    [(True, True), (False, False), ("true", True), ("false", False)],
)
def test_is_abstract_se_convierte_a_booleano_y_no_por_truthiness(client, raw, esperado):
    # Se parte del estado opuesto al esperado para que el test detecte "no cambió nada".
    canvas_id, version = _canvas_con_clase(client, is_abstract=not esperado)

    res = _update_class(client, canvas_id, version, isAbstract=raw)

    assert res.status_code == 200
    assert _is_abstract(res) is esperado


@pytest.mark.parametrize("raw", ["banana", 2, ["false"]])
def test_is_abstract_invalido_se_rechaza_y_no_modifica_la_clase(client, raw):
    canvas_id, version = _canvas_con_clase(client, is_abstract=False)

    res = _update_class(client, canvas_id, version, isAbstract=raw)

    assert res.status_code in (400, 422)
    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["version"] == version
    clase = next(c for c in persisted["model"]["classes"] if c["id"] == CLASS_ID)
    assert clase["isAbstract"] is False


def test_sin_is_abstract_el_renombrado_no_toca_la_abstraccion(client):
    canvas_id, version = _canvas_con_clase(client, is_abstract=True)

    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "UPDATE_CLASS_NAME",
            "payload": {"classId": CLASS_ID, "name": "FiguraGeometrica"},
        },
    )

    assert res.status_code == 200
    assert _is_abstract(res) is True
