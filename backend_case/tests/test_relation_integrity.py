import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client



def test_cannot_create_duplicate_relation_between_same_classes(client: TestClient) -> None:
    # 1. Crear lienzo y dos clases
    resp = client.post("/api/v2/canvases", json={"name": "Lienzo Test Duplicados"})
    canvas_id = resp.json()["id"]

    c1_resp = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={"expectedVersion": 1, "type": "CREATE_CLASS", "payload": {"name": "Cliente"}},
    )
    c1_id = c1_resp.json()["canvas"]["model"]["classes"][0]["id"]

    c2_resp = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={"expectedVersion": 2, "type": "CREATE_CLASS", "payload": {"name": "Factura"}},
    )
    c2_id = next(
        c["id"] for c in c2_resp.json()["canvas"]["model"]["classes"] if c["name"] == "Factura"
    )

    # 2. Crear primera relación entre Cliente y Factura -> 200 OK
    rel1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": c1_id,
                "targetClassId": c2_id,
                "type": "ASSOCIATION",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "0..*",
            },
        },
    )
    assert rel1.status_code == 200
    assert len(rel1.json()["canvas"]["model"]["associations"]) == 1

    # 3. Intentar crear una SEGUNDA relación entre el mismo par (en sentido directo) -> 422
    dup1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 4,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": c1_id,
                "targetClassId": c2_id,
                "type": "ASSOCIATION",
            },
        },
    )
    assert dup1.status_code == 422
    assert dup1.json()["code"] == "UML_INVALID_MODEL"
    assert "Ya existe una relación" in dup1.json()["message"]

    # 4. Intentar crear una relación en sentido inverso (Factura -> Cliente) -> 422
    dup2 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 4,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": c2_id,
                "targetClassId": c1_id,
                "type": "DEPENDENCY",
            },
        },
    )
    assert dup2.status_code == 422
    assert "Ya existe una relación" in dup2.json()["message"]


def test_reflexive_relation_is_accepted_once_and_blocks_second(client: TestClient) -> None:
    # 1. Crear lienzo y clase Empleado
    resp = client.post("/api/v2/canvases", json={"name": "Lienzo Test Reflexiva"})
    canvas_id = resp.json()["id"]

    c1_resp = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={"expectedVersion": 1, "type": "CREATE_CLASS", "payload": {"name": "Empleado"}},
    )
    c1_id = c1_resp.json()["canvas"]["model"]["classes"][0]["id"]

    # 2. Primera relación reflexiva: Empleado -> Empleado -> 200 OK
    rel1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": c1_id,
                "targetClassId": c1_id,
                "type": "ASSOCIATION",
                "name": "supervisa",
                "sourceMultiplicity": "0..1",
                "targetMultiplicity": "*",
            },
        },
    )
    assert rel1.status_code == 200
    assocs = rel1.json()["canvas"]["model"]["associations"]
    assert len(assocs) == 1
    assert assocs[0]["name"] == "supervisa"
    assert assocs[0]["memberEnds"][0]["classId"] == c1_id
    assert assocs[0]["memberEnds"][1]["classId"] == c1_id

    # 3. Intentar crear una SEGUNDA relación reflexiva en la misma clase -> 422
    dup_rel = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": c1_id,
                "targetClassId": c1_id,
                "type": "ASSOCIATION",
            },
        },
    )
    assert dup_rel.status_code == 422
    assert "Ya existe una relación" in dup_rel.json()["message"]
