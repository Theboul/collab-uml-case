"""
Pruebas para creación de lienzos UML (CU1), resolución por sala y ejecución de comandos con control de concurrencia optimista.
"""

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_create_canvas_cu1_initial_state(client: TestClient):
    """Verifica que el lienzo se crea con modelo vacío, layout inicial y roomName único."""
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Inicial", "description": "Prueba CU1"})
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Lienzo Inicial"
    assert data["version"] == 1
    assert data["model"]["classes"] == []
    assert data["model"]["associations"] == []
    assert data["model"]["generalizations"] == []
    assert data["roomName"] is not None
    assert data["roomName"].startswith("room-")
    assert "viewport" in data["visualLayout"]


def test_get_canvas_by_room_code(client: TestClient):
    """Verifica la resolución de un lienzo a partir de su roomName."""
    create_res = client.post("/api/v2/canvases", json={"name": "Lienzo Por Sala"})
    assert create_res.status_code == 201
    room_name = create_res.json()["roomName"]

    by_room_res = client.get(f"/api/v2/canvases/by-room/{room_name}")
    assert by_room_res.status_code == 200
    data = by_room_res.json()
    assert data["id"] == create_res.json()["id"]
    assert data["roomName"] == room_name


def test_execute_commands_lifecycle_and_versioning(client: TestClient):
    """Verifica el ciclo de vida de comandos: CREATE_CLASS, MOVE, RESIZE, CREATE_RELATION, UPDATE, DELETE."""
    # 1. Crear lienzo (v=1)
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Comandos"})
    canvas_id = res.json()["id"]
    version = res.json()["version"]
    assert version == 1

    # 2. CREATE_CLASS (v=1 -> v=2)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"name": "Cliente", "x": 120, "y": 80, "width": 180, "height": 100},
        },
    )
    assert cmd_res.status_code == 200
    data = cmd_res.json()
    assert data["accepted"] is True
    assert data["version"] == 2
    classes = data["canvas"]["model"]["classes"]
    assert len(classes) == 1
    cliente_id = classes[0]["id"]
    assert classes[0]["name"] == "Cliente"
    assert str(cliente_id) in data["canvas"]["visualLayout"]["nodes"]
    assert data["canvas"]["visualLayout"]["nodes"][str(cliente_id)]["x"] == 120

    # 3. CREATE_CLASS para Pedido (v=2 -> v=3)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_CLASS",
            "payload": {"name": "Pedido", "x": 400, "y": 80},
        },
    )
    assert cmd_res.status_code == 200
    pedido_id = cmd_res.json()["canvas"]["model"]["classes"][1]["id"]
    assert cmd_res.json()["version"] == 3

    # 4. MOVE_ELEMENT en Pedido (v=3 -> v=4)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "MOVE_ELEMENT",
            "payload": {"elementId": pedido_id, "x": 450, "y": 150},
        },
    )
    assert cmd_res.status_code == 200
    assert cmd_res.json()["version"] == 4
    assert cmd_res.json()["canvas"]["visualLayout"]["nodes"][str(pedido_id)]["x"] == 450

    # 5. RESIZE_ELEMENT (v=4 -> v=5)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 4,
            "type": "RESIZE_ELEMENT",
            "payload": {"elementId": cliente_id, "width": 200, "height": 130},
        },
    )
    assert cmd_res.status_code == 200
    assert cmd_res.json()["version"] == 5
    assert cmd_res.json()["canvas"]["visualLayout"]["nodes"][str(cliente_id)]["width"] == 200

    # 6. CREATE_RELATION (v=5 -> v=6)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 5,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": cliente_id,
                "targetClassId": pedido_id,
                "type": "ASSOCIATION",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "0..*",
            },
        },
    )
    assert cmd_res.status_code == 200
    assert cmd_res.json()["version"] == 6
    assocs = cmd_res.json()["canvas"]["model"]["associations"]
    assert len(assocs) == 1
    rel_id = assocs[0]["id"]

    # 7. UPDATE_RELATION (v=6 -> v=7)
    cmd_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 6,
            "type": "UPDATE_RELATION",
            "payload": {
                "relationId": rel_id,
                "type": "AGGREGATION",
                "sourceMultiplicity": "1",
                "targetMultiplicity": "1..*",
            },
        },
    )
    assert cmd_res.status_code == 200
    assert cmd_res.json()["version"] == 7

    # 8. VERSION CONFLICT: enviar expectedVersion errónea debe responder 409
    conflict_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,  # actual es 7
            "type": "MOVE_ELEMENT",
            "payload": {"elementId": cliente_id, "x": 0, "y": 0},
        },
    )
    assert conflict_res.status_code == 409
    err = conflict_res.json()
    assert err["code"] == "VERSION_CONFLICT"

    # 9. DELETE_ELEMENT de Cliente (v=7 -> v=8) - debe eliminar la clase y relaciones asociadas
    del_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 7,
            "type": "DELETE_ELEMENT",
            "payload": {"elementId": cliente_id},
        },
    )
    assert del_res.status_code == 200
    assert del_res.json()["version"] == 8
    model = del_res.json()["canvas"]["model"]
    assert len(model["classes"]) == 1
    assert model["classes"][0]["id"] == pedido_id
    assert len(model["associations"]) == 0


def test_create_generalization_relation_command(client: TestClient):
    """CU4: Verificar que CREATE_RELATION con type GENERALIZATION crea una generalización en el modelo."""
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Herencia"})
    assert res.status_code == 201
    canvas_id = res.json()["id"]

    # Crear superclase y subclase
    cmd1 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"name": "Persona", "x": 100, "y": 100},
        },
    )
    persona_id = cmd1.json()["canvas"]["model"]["classes"][0]["id"]

    cmd2 = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_CLASS",
            "payload": {"name": "Empleado", "x": 100, "y": 300},
        },
    )
    empleado_id = cmd2.json()["canvas"]["model"]["classes"][1]["id"]

    # Crear generalización Empleado -> Persona
    gen_cmd = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": empleado_id,
                "targetClassId": persona_id,
                "type": "GENERALIZATION",
            },
        },
    )
    assert gen_cmd.status_code == 200
    data = gen_cmd.json()
    assert data["accepted"] is True
    assert data["version"] == 4
    generalizations = data["canvas"]["model"]["generalizations"]
    assert len(generalizations) == 1
    assert generalizations[0]["specificClassId"] == empleado_id
    assert generalizations[0]["generalClassId"] == persona_id


def test_update_relation_layout_persists_manual_port_override(client: TestClient):
    """
    Verifica que UPDATE_RELATION_LAYOUT guarda el puerto elegido manualmente en
    visualLayout.links, sin tocar el modelo de dominio (associations/generalizations
    quedan intactos), y que ese valor persiste en una recarga posterior del lienzo.
    """
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Reconexion"})
    canvas_id = res.json()["id"]

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-a", "name": "ClaseA"},
        },
    )
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-b", "name": "ClaseB"},
        },
    )
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "relationId": "rel-a-b",
                "sourceClassId": "c-a",
                "targetClassId": "c-b",
                "type": "ASSOCIATION",
            },
        },
    )

    layout_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 4,
            "type": "UPDATE_RELATION_LAYOUT",
            "payload": {
                "relationId": "rel-a-b",
                "sourcePort": "port-bottom-2",
                "targetPort": "port-bottom-0",
            },
        },
    )
    assert layout_res.status_code == 200
    data = layout_res.json()
    links = data["canvas"]["visualLayout"]["links"]
    assert links["rel-a-b"]["sourcePort"] == "port-bottom-2"
    assert links["rel-a-b"]["targetPort"] == "port-bottom-0"
    # No debe alterar el modelo de dominio, solo el layout visual.
    assert len(data["canvas"]["model"]["associations"]) == 1

    reloaded = client.get(f"/api/v2/canvases/{canvas_id}")
    assert reloaded.status_code == 200
    reloaded_links = reloaded.json()["visualLayout"]["links"]
    assert reloaded_links["rel-a-b"]["sourcePort"] == "port-bottom-2"
    assert reloaded_links["rel-a-b"]["targetPort"] == "port-bottom-0"


def test_update_relation_vertices_persists_manual_path(client: TestClient):
    """
    Verifica que UPDATE_RELATION_VERTICES guarda los vértices intermedios arrastrados a mano
    en visualLayout.links, sin tocar el modelo de dominio.
    """
    res = client.post("/api/v2/canvases", json={"name": "Lienzo Vertices"})
    canvas_id = res.json()["id"]

    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 1,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-a", "name": "ClaseA"},
        },
    )
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 2,
            "type": "CREATE_CLASS",
            "payload": {"classId": "c-b", "name": "ClaseB"},
        },
    )
    client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 3,
            "type": "CREATE_RELATION",
            "payload": {
                "relationId": "rel-a-b",
                "sourceClassId": "c-a",
                "targetClassId": "c-b",
                "type": "ASSOCIATION",
            },
        },
    )

    vertices_res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": 4,
            "type": "UPDATE_RELATION_VERTICES",
            "payload": {
                "relationId": "rel-a-b",
                "vertices": [{"x": 120.0, "y": 340.0}, {"x": 200.0, "y": 340.0}],
            },
        },
    )
    assert vertices_res.status_code == 200
    data = vertices_res.json()
    links = data["canvas"]["visualLayout"]["links"]
    assert links["rel-a-b"]["vertices"] == [
        {"x": 120.0, "y": 340.0},
        {"x": 200.0, "y": 340.0},
    ]
    # No debe alterar el modelo de dominio, solo el layout visual.
    assert len(data["canvas"]["model"]["associations"]) == 1

    reloaded = client.get(f"/api/v2/canvases/{canvas_id}")
    assert reloaded.status_code == 200
    reloaded_links = reloaded.json()["visualLayout"]["links"]
    assert reloaded_links["rel-a-b"]["vertices"] == [
        {"x": 120.0, "y": 340.0},
        {"x": 200.0, "y": 340.0},
    ]

