"""
Pruebas de integración API para el módulo de modelado UML (CU1 - CU4) en FastAPI.
Verifica persistencia, reglas de negocio UML, incremento de versión y formato unificado de error.
"""

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_create_canvas_cu1(client: TestClient):
    """CU1: Crear nuevo lienzo UML."""
    response = client.post(
        "/api/v2/canvases",
        json={"name": "Sistema de Ventas", "description": "Diagrama de prueba"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == "Sistema de Ventas"
    assert data["description"] == "Diagrama de prueba"
    assert data["version"] == 1
    assert data["model"]["classes"] == []
    assert data["model"]["associations"] == []


def test_get_canvas_cu2(client: TestClient):
    """CU2: Obtener lienzo existente por ID."""
    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Consulta", "description": "Test get"},
    )
    canvas_id = create_res.json()["id"]

    get_res = client.get(f"/api/v2/canvases/{canvas_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == canvas_id
    assert data["name"] == "Lienzo Consulta"


def test_get_nonexistent_canvas_returns_404(client: TestClient):
    """Verifica manejo canónico de error cuando el lienzo no existe."""
    response = client.get("/api/v2/canvases/non-existent-canvas-id-999")
    assert response.status_code == 404
    data = response.json()
    assert data["code"] == "CANVAS_NOT_FOUND"
    assert "no encontrado" in data["message"].lower()


def test_add_class_cu3(client: TestClient):
    """CU3: Agregar clase a un lienzo y verificar incremento de versión."""
    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Clases"},
    )
    canvas_id = create_res.json()["id"]

    add_res = client.post(
        f"/api/v2/canvases/{canvas_id}/classes",
        json={"name": "Cliente", "isAbstract": False},
    )
    assert add_res.status_code == 201
    data = add_res.json()
    assert data["version"] == 2
    assert len(data["model"]["classes"]) == 1
    assert data["model"]["classes"][0]["name"] == "Cliente"
    assert data["model"]["classes"][0]["isAbstract"] is False


def test_add_duplicate_class_returns_422(client: TestClient):
    """CU3: Rechazar clases con nombre duplicado retornando error canónico 422."""
    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Duplicados"},
    )
    canvas_id = create_res.json()["id"]

    # Agregar primera vez
    client.post(
        f"/api/v2/canvases/{canvas_id}/classes",
        json={"name": "Producto"},
    )

    # Intentar agregar duplicado
    dup_res = client.post(
        f"/api/v2/canvases/{canvas_id}/classes",
        json={"name": "Producto"},
    )
    assert dup_res.status_code == 422
    data = dup_res.json()
    assert data["code"] == "UML_INVALID_MODEL"
    assert "ya existe un clasificador" in data["message"].lower()


def test_add_association_cu4(client: TestClient):
    """CU4: Agregar asociación binaria entre dos clases."""
    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Asociaciones"},
    )
    canvas_id = create_res.json()["id"]

    c1 = client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Pedido"}).json()
    c2 = client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Factura"}).json()

    pedido_id = c1["model"]["classes"][0]["id"]
    factura_id = next(c["id"] for c in c2["model"]["classes"] if c["name"] == "Factura")

    assoc_res = client.post(
        f"/api/v2/canvases/{canvas_id}/associations",
        json={
            "sourceClassId": pedido_id,
            "targetClassId": factura_id,
            "name": "genera",
            "sourceRole": "origen",
            "targetRole": "destino",
            "sourceMultiplicity": "1",
            "targetMultiplicity": "0..1",
            "sourceAggregation": "none",
            "targetAggregation": "none",
        },
    )
    assert assoc_res.status_code == 201
    data = assoc_res.json()
    assert len(data["model"]["associations"]) == 1
    assoc = data["model"]["associations"][0]
    assert assoc["name"] == "genera"
    assert len(assoc["memberEnds"]) == 2
    assert assoc["memberEnds"][0]["classId"] == pedido_id
    assert assoc["memberEnds"][1]["classId"] == factura_id
    assert assoc["memberEnds"][1]["multiplicity"]["lowerBound"] == 0
    assert assoc["memberEnds"][1]["multiplicity"]["upperBound"] == 1


def test_add_association_with_nonexistent_class_returns_404(client: TestClient):
    """CU4: Rechazar asociación si una de las clases no existe."""
    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Error Asoc"},
    )
    canvas_id = create_res.json()["id"]
    c1 = client.post(f"/api/v2/canvases/{canvas_id}/classes", json={"name": "Item"}).json()
    item_id = c1["model"]["classes"][0]["id"]

    assoc_res = client.post(
        f"/api/v2/canvases/{canvas_id}/associations",
        json={
            "sourceClassId": item_id,
            "targetClassId": "id-inexistente",
            "name": "rel",
        },
    )
    assert assoc_res.status_code == 404
    data = assoc_res.json()
    assert data["code"] == "ELEMENT_NOT_FOUND"


def test_list_canvases(client: TestClient):
    """Listar lienzos existentes."""
    res = client.get("/api/v2/canvases")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
