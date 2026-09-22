"""
Pruebas de integración de CU6: POST /api/v2/canvases/{id}/assistant/text-command.
Verifica que una respuesta de Gemini con forma de creación termina como
clases/relaciones reales y validadas en el lienzo, y que una respuesta con
forma de operaciones (edición/eliminación por nombre sobre un modelo
existente) se aplica de forma atómica -- o se rechaza entera, sin mutar nada,
si alguna operación no resuelve.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_canvas(client: TestClient) -> tuple[str, int]:
    res = client.post("/api/v2/canvases", json={"name": "Lienzo CU6"})
    assert res.status_code == 201
    data = res.json()
    return data["id"], data["version"]


def _seed_class_with_attribute(
    client: TestClient,
    canvas_id: str,
    version: int,
    class_name: str,
    attr_name: str,
    attr_type: str,
) -> int:
    """Crea una clase con un atributo vía el pipeline real de comandos (CU3), para
    tener un modelo existente real contra el cual resolver operaciones de IA."""
    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"name": class_name, "x": 100, "y": 100},
        },
    )
    assert res.status_code == 200
    version = res.json()["version"]
    class_id = res.json()["canvas"]["model"]["classes"][0]["id"]

    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_ATTRIBUTE",
            "payload": {"classId": class_id, "name": attr_name, "type": attr_type},
        },
    )
    assert res.status_code == 200
    return res.json()["version"]


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


def test_text_command_operations_rename_and_add_attribute_chained(client: TestClient):
    """
    Escenario real de la ficha: "cambia el nombre de Usuario a Cliente y
    agregale un atributo telefono de tipo String" -- la segunda operación
    referencia el nombre NUEVO ('Cliente'), que solo existe después de que la
    primera ya se despachó. Confirma resolución secuencial real, no solo
    contra una foto fija del modelo previa al lote.
    """
    canvas_id, version = _create_canvas(client)
    version = _seed_class_with_attribute(client, canvas_id, version, "Usuario", "email", "String")

    operations_response = json.dumps(
        {
            "operations": [
                {"action": "rename_class", "target": "Usuario", "newName": "Cliente"},
                {
                    "action": "add_attribute",
                    "target": "Cliente",
                    "name": "telefono",
                    "type": "String",
                },
            ]
        }
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ) as mock_call:
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={
                "prompt": (
                    "cambia el nombre de la clase Usuario a Cliente y agregale un "
                    "atributo telefono de tipo String"
                ),
                "expectedVersion": version,
            },
        )

    assert res.status_code == 200
    data = res.json()
    # Un solo guardado atómico para las dos operaciones del lote, no dos.
    assert data["version"] == version + 1

    classes = data["canvas"]["model"]["classes"]
    assert len(classes) == 1
    cliente = classes[0]
    assert cliente["name"] == "Cliente"
    attr_names = {a["name"] for a in cliente["attributes"]}
    assert attr_names == {"email", "telefono"}

    # El contexto del modelo actual (antes del rename) se le pasó a Gemini.
    _, kwargs = mock_call.call_args
    assert kwargs["model_context"]["classes"][0]["name"] == "Usuario"


def test_text_command_operations_batch_is_all_or_nothing(client: TestClient):
    """
    Una operación inválida en el medio de un lote (referencia un atributo que
    no existe) no debe dejar aplicada ninguna de las otras, ni siquiera las
    que resolvían correctamente antes de ella.
    """
    canvas_id, version = _create_canvas(client)
    version = _seed_class_with_attribute(client, canvas_id, version, "Usuario", "email", "String")

    operations_response = json.dumps(
        {
            "operations": [
                {"action": "rename_class", "target": "Usuario", "newName": "Cliente"},
                {"action": "delete_attribute", "target": "Cliente", "attribute": "no_existe"},
            ]
        }
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={
                "prompt": "cambia el nombre de Usuario a Cliente y elimina el atributo no_existe",
                "expectedVersion": version,
            },
        )

    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "UML_INVALID_MODEL"
    assert "Operación #2" in body["message"]

    # Ni el rename (operación #1, válida) ni nada más quedó aplicado.
    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["model"]["classes"][0]["name"] == "Usuario"
    assert persisted["version"] == version


def test_text_command_operations_lists_all_failures_not_just_first(client: TestClient):
    canvas_id, version = _create_canvas(client)
    version = _seed_class_with_attribute(client, canvas_id, version, "Usuario", "email", "String")

    operations_response = json.dumps(
        {
            "operations": [
                {"action": "delete_attribute", "target": "Usuario", "attribute": "no_existe_1"},
                {"action": "delete_class", "target": "Inexistente"},
            ]
        }
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={
                "prompt": (
                    "elimina el atributo no_existe_1 de Usuario y elimina la clase Inexistente"
                ),
                "expectedVersion": version,
            },
        )

    assert res.status_code == 422
    message = res.json()["message"]
    assert "Operación #1" in message
    assert "Operación #2" in message

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["version"] == version


def _seed_bare_class(client: TestClient, canvas_id: str, version: int, class_name: str) -> int:
    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"name": class_name, "x": 100, "y": 100},
        },
    )
    assert res.status_code == 200
    return res.json()["version"]


def test_text_command_rename_class_to_its_own_name_is_a_noop_not_a_false_collision(
    client: TestClient,
):
    """
    find_classifier_by_name encuentra la propia clase al buscar su nombre
    actual; el chequeo de colisión de UPDATE_CLASS_NAME (class_handlers.py)
    ya excluye explícitamente ese caso (otro.id != cmd.classId), así que
    "renombrar" una clase al mismo nombre que ya tiene no debe rechazarse
    como si colisionara consigo misma.
    """
    canvas_id, version = _create_canvas(client)
    version = _seed_bare_class(client, canvas_id, version, "Usuario")

    operations_response = json.dumps(
        {"operations": [{"action": "rename_class", "target": "Usuario", "newName": "Usuario"}]}
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={"prompt": "no cambies nada de Usuario", "expectedVersion": version},
        )

    assert res.status_code == 200
    assert res.json()["canvas"]["model"]["classes"][0]["name"] == "Usuario"


def test_text_command_rename_class_colliding_with_another_existing_class_rejected(
    client: TestClient,
):
    """
    A diferencia del caso anterior, renombrar 'Usuario' a 'Rol' cuando 'Rol'
    YA EXISTE como una clase distinta sí debe rechazarse -- acá el chequeo de
    colisión de UPDATE_CLASS_NAME encuentra un classifier con id distinto al
    que se está renombrando, y ese caso real de colisión no se excluye.
    """
    canvas_id, version = _create_canvas(client)
    version = _seed_bare_class(client, canvas_id, version, "Usuario")
    version = _seed_bare_class(client, canvas_id, version, "Rol")

    operations_response = json.dumps(
        {"operations": [{"action": "rename_class", "target": "Usuario", "newName": "Rol"}]}
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={"prompt": "cambiale el nombre a Usuario por Rol", "expectedVersion": version},
        )

    assert res.status_code == 422
    assert res.json()["code"] == "UML_INVALID_MODEL"

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    persisted_names = {c["name"] for c in persisted["model"]["classes"]}
    assert persisted_names == {"Usuario", "Rol"}
    assert persisted["version"] == version


def test_text_command_malformed_action_field_returns_422_not_500(client: TestClient):
    """
    Defensa en profundidad de extremo a extremo: aunque gemini_command_mapper
    ya valide el tipo de 'action' antes de esta iteración, este test prueba
    que la ruta completa (CanvasService.ejecutar_resolviendo_secuencial) nunca
    deja escapar un error no-UmlDomainError como 500 -- lo trata igual que
    cualquier otra operación fallida.
    """
    canvas_id, version = _create_canvas(client)
    version = _seed_bare_class(client, canvas_id, version, "Usuario")

    operations_response = json.dumps({"operations": [{"action": ["rename_class"]}]})

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{operations_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={"prompt": "cambiale el nombre a Usuario", "expectedVersion": version},
        )

    assert res.status_code == 422
    assert res.json()["code"] == "UML_INVALID_MODEL"
    assert "Operación #1" in res.json()["message"]

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["version"] == version


def test_text_command_explanation_returns_message_without_mutating_model(client: TestClient):
    canvas_id, version = _create_canvas(client)
    version = _seed_bare_class(client, canvas_id, version, "Usuario")

    explanation_response = json.dumps(
        {
            "type": "explanation",
            "message": "El diagrama tiene una clase Usuario con identificador único.",
        }
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini",
        return_value=f"```json\n{explanation_response}\n```",
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/text-command",
            json={"prompt": "¿Qué clases tiene mi diagrama?", "expectedVersion": version},
        )

    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] is True
    assert body["version"] == version
    assert "Usuario con identificador" in body["message"]

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["version"] == version
    assert len(persisted["model"]["classes"]) == 1

