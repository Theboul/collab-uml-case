"""
Pruebas de integración de CU6: POST /api/v2/canvases/{id}/assistant/text-command.
Verifica que una respuesta de Gemini con forma de creación termina como
clases/relaciones reales y validadas en el lienzo, y que una respuesta con
forma de edición se rechaza con 422 y el mensaje de limitación claro --
sin mutar el modelo persistido.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.assistant.application.gemini_command_mapper import (
    EDIT_OR_DELETE_MESSAGE,
)
from backend_case.app.main import app

CREATION_RESPONSE = json.dumps(
    {
        "classes": [
            {
                "id": "c1",
                "name": "Usuario",
                "attributes": [{"name": "email", "type": "String"}],
                "methods": [
                    {"name": "autenticar", "parameters": "clave: String", "returnType": "Boolean"}
                ],
            },
            {
                "id": "c2",
                "name": "Rol",
                "attributes": [{"name": "nombre", "type": "String"}],
                "methods": [],
            },
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["*", "1"],
            }
        ],
    }
)

EDIT_RESPONSE = json.dumps({"original": {"classes": []}, "editado": {"editado": True}})


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_canvas(client: TestClient) -> tuple[str, int]:
    res = client.post("/api/v2/canvases", json={"name": "Lienzo CU6"})
    assert res.status_code == 201
    data = res.json()
    return data["id"], data["version"]


def test_text_command_creation_maps_to_validated_model(client: TestClient):
    canvas_id, version = _create_canvas(client)

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{CREATION_RESPONSE}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={
                "prompt": "Crea las clases Usuario y Rol relacionadas",
                "expectedVersion": version,
            },
        )

    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["version"] == version + 1

    classes = data["canvas"]["model"]["classes"]
    assert {c["name"] for c in classes} == {"Usuario", "Rol"}
    usuario = next(c for c in classes if c["name"] == "Usuario")
    assert usuario["attributes"][0]["name"] == "email"
    assert usuario["operations"][0]["name"] == "autenticar"
    assert usuario["operations"][0]["parameters"][0] == {
        "id": usuario["operations"][0]["parameters"][0]["id"],
        "name": "clave",
        "type": "String",
        "direction": "in",
        "defaultValue": None,
    }

    associations = data["canvas"]["model"]["associations"]
    assert len(associations) == 1

    # El lienzo persistido refleja el mismo estado (no quedó solo en la respuesta HTTP).
    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert len(persisted["model"]["classes"]) == 2
    assert persisted["version"] == version + 1


def test_text_command_edit_shape_rejected_with_clear_message_and_no_mutation(client: TestClient):
    canvas_id, version = _create_canvas(client)

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{EDIT_RESPONSE}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={"prompt": "Cambiale el nombre a la clase Usuario", "expectedVersion": version},
        )

    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "UML_INVALID_MODEL"
    assert body["message"] == EDIT_OR_DELETE_MESSAGE

    # El modelo persistido no cambió: ni clases nuevas ni avance de versión.
    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["model"]["classes"] == []
    assert persisted["version"] == version
