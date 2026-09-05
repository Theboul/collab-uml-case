"""
Pruebas de endpoints HTTP de FastAPI backend_case (API-01 a API-09 de SPEC-06).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend_case.app.application.mappers import DomainToPydanticMapper
from backend_case.app.main import app
from core.uml_domain.adapters.legacy_input_adapter import LegacyInputAdapter

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_LEGACY_DIR = REPO_ROOT / "tests" / "fixtures" / "legacy"
FIXTURES_V2_DIR = REPO_ROOT / "tests" / "fixtures" / "v2"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def f01_v2_payload():
    with open(FIXTURES_LEGACY_DIR / "F01-simple-class.json", "r", encoding="utf-8") as f:
        legacy_data = json.load(f)
    domain_model = LegacyInputAdapter.to_v2_model(legacy_data, model_name="ClienteModel")
    pydantic_schema = DomainToPydanticMapper.to_pydantic_schema(domain_model)
    return pydantic_schema.model_dump(by_alias=True)


@pytest.fixture
def v01_v2_payload():
    with open(FIXTURES_V2_DIR / "V01-interface-realization.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_api_01_health_check(client):
    """API-01: GET /health devuelve 200 y status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_02_info_endpoint(client):
    """API-02: GET /api/v2/info devuelve metadatos del servicio y versión de esquema."""
    resp = client.get("/api/v2/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["service"] == "CASE Backend"
    assert data["apiVersion"] == "2"
    assert data["umlSchemaVersion"] == "2.0.0"


def test_api_03_validate_valid_model(client, f01_v2_payload):
    """API-03: POST /api/v2/uml/validate con modelo válido devuelve valid=true y 0 errores."""
    resp = client.post("/api/v2/uml/validate", json=f01_v2_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["errors"]) == 0


def test_api_04_validate_duplicate_id(client, f01_v2_payload):
    """API-04: Modelo con ID duplicado devuelve valid=false y código VUML-02."""
    payload = f01_v2_payload.copy()
    # Duplicar la clase con el mismo ID pero distinto nombre
    dup_class = payload["classes"][0].copy()
    dup_class["name"] = "ClienteDuplicado"
    payload["classes"].append(dup_class)

    resp = client.post("/api/v2/uml/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any(err["code"] == "VUML-02" for err in data["errors"])


def test_api_05_validate_circular_generalization(client):
    """API-05: Generalización circular devuelve valid=false y error VUML-07."""
    payload = {
        "schemaVersion": "2.0.0",
        "modelId": "uuid-cyclic-test",
        "name": "CicloHerencia",
        "classes": [
            {"id": "cls-a", "name": "ClaseA", "visibility": "+", "attributes": [], "operations": []},
            {"id": "cls-b", "name": "ClaseB", "visibility": "+", "attributes": [], "operations": []},
        ],
        "associations": [],
        "generalizations": [
            {"id": "gen-1", "specificClassId": "cls-a", "generalClassId": "cls-b"},
            {"id": "gen-2", "specificClassId": "cls-b", "generalClassId": "cls-a"},
        ],
        "realizations": [],
        "dependencies": [],
    }
    resp = client.post("/api/v2/uml/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any(err["code"] == "VUML-07" for err in data["errors"])


def test_api_06_validate_realization_to_non_interface(client):
    """API-06: Realization apuntando a una clase concreta (no interfaz) devuelve error VUML-09."""
    payload = {
        "schemaVersion": "2.0.0",
        "modelId": "uuid-realiz-test",
        "name": "RealizInvalida",
        "classes": [
            {"id": "cls-c1", "name": "Servicio", "isInterface": False, "attributes": [], "operations": []},
            {"id": "cls-c2", "name": "Concreto", "isInterface": False, "attributes": [], "operations": []},
        ],
        "associations": [],
        "generalizations": [],
        "realizations": [
            {"id": "realiz-1", "clientClassId": "cls-c1", "supplierInterfaceId": "cls-c2"},
        ],
        "dependencies": [],
    }
    resp = client.post("/api/v2/uml/validate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is False
    assert any(err["code"] == "VUML-09" for err in data["errors"])


def test_api_07_spring_compatibility_valid_model(client, f01_v2_payload):
    """API-07: Modelo compatible con Spring Boot v1 devuelve valid=true."""
    resp = client.post("/api/v2/uml/compatibility/spring", json=f01_v2_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["errors"]) == 0


def test_api_08_spring_compatibility_unsupported_feature(client, v01_v2_payload):
    """
    API-08: Feature V2 no soportada por Spring Boot v1 (UmlInterface / UmlRealization)
    devuelve advertencia/degradación informando la incompatibilidad.
    """
    resp = client.post("/api/v2/uml/compatibility/spring", json=v01_v2_payload)
    assert resp.status_code == 200
    data = resp.json()
    # Debe contener advertencia VGEN-SB-03 sobre interfaces no generadas en plantillas v1
    assert any(w["code"] == "VGEN-SB-03" for w in data["warnings"])


def test_api_09_flutter_compatibility_valid_model(client, f01_v2_payload):
    """API-09: Modelo compatible con Flutter CRUD devuelve resultado esperado."""
    resp = client.post("/api/v2/uml/compatibility/flutter", json=f01_v2_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["valid"] is True
    assert len(data["errors"]) == 0
