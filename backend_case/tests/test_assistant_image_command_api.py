"""
Pruebas de integración de CU7: POST /api/v2/canvases/{id}/assistant/image-command.
Reutiliza el mismo pipeline de comandos que CU6 texto (map_gemini_response_to_commands
+ CanvasService.ejecutar_comandos_lote) -- estas pruebas mockean call_gemini_from_image
(no hace falta reconocimiento de imagen real para probar el cableado) y confirman:
una imagen que Gemini interpreta bien termina en clases/relaciones reales y validadas,
y una imagen ilegible ({"error": ...}) se rechaza con 422 explícito sin mutar nada.
"""

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app

CREATION_RESULT = {
    "classes": [
        {
            "id": "c1",
            "name": "Usuario",
            "attributes": [{"name": "email", "type": "String"}],
            "methods": [],
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

DUMMY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_canvas(client: TestClient) -> tuple[str, int]:
    res = client.post("/api/v2/canvases", json={"name": "Lienzo CU7"})
    assert res.status_code == 201
    data = res.json()
    return data["id"], data["version"]


def test_image_command_creation_maps_to_validated_model(client: TestClient):
    canvas_id, version = _create_canvas(client)

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini_from_image",
        return_value=CREATION_RESULT,
    ) as mock_call:
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/image-command",
            files={"image": ("diagrama.png", io.BytesIO(DUMMY_PNG), "image/png")},
            data={"expectedVersion": str(version)},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] is True
    assert data["version"] == version + 1

    classes = data["canvas"]["model"]["classes"]
    assert {c["name"] for c in classes} == {"Usuario", "Rol"}
    associations = data["canvas"]["model"]["associations"]
    assert len(associations) == 1

    # call_gemini_from_image recibe base64 + mime_type, no un prompt de texto.
    args, kwargs = mock_call.call_args
    assert isinstance(args[0], str)  # image_base64
    assert kwargs.get("mime_type") == "image/png" or args[1:] == ("image/png",)

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert len(persisted["model"]["classes"]) == 2
    assert persisted["version"] == version + 1


def test_image_command_unreadable_image_rejected_with_clear_message_and_no_mutation(
    client: TestClient,
):
    canvas_id, version = _create_canvas(client)

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini_from_image",
        return_value={"error": "No se pudo parsear correctamente"},
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/image-command",
            files={"image": ("borrosa.png", io.BytesIO(DUMMY_PNG), "image/png")},
            data={"expectedVersion": str(version)},
        )

    assert res.status_code == 422
    body = res.json()
    assert body["code"] == "UML_INVALID_MODEL"
    assert "No se pudo interpretar la imagen" in body["message"]

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["model"]["classes"] == []
    assert persisted["version"] == version


def test_image_command_never_leaks_gemini_error_detail_to_client(client: TestClient):
    """
    call_gemini_from_image atrapa sus propias excepciones y devuelve
    {"error": str(e)} -- para errores HTTP de `requests`, ese string incluye
    la URL completa de la request, con la API key de Gemini en el query
    string (confirmado real contra la API). El valor acá es sintético (no una
    key real, ni siquiera una ya rotada) -- alcanza con probar que CUALQUIER
    string con esa forma nunca llega al cliente, sin dejar un fragmento de
    credencial real en el repo.
    """
    canvas_id, version = _create_canvas(client)

    leaky_detail = (
        "400 Client Error: Bad Request for url: "
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-lite-latest:generateContent?key=AQ.FakeSyntheticKeyForTestingOnly123"
    )

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini_from_image",
        return_value={"error": leaky_detail},
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/image-command",
            files={"image": ("borrosa.png", io.BytesIO(DUMMY_PNG), "image/png")},
            data={"expectedVersion": str(version)},
        )

    assert res.status_code == 422
    body_text = res.text
    assert "key=" not in body_text
    assert "FakeSyntheticKeyForTestingOnly123" not in body_text
    assert "generativelanguage.googleapis.com" not in body_text


def test_image_command_rejects_empty_file(client: TestClient):
    canvas_id, version = _create_canvas(client)

    res = client.post(
        f"/api/v2/canvases/{canvas_id}/assistant/image-command",
        files={"image": ("vacia.png", io.BytesIO(b""), "image/png")},
        data={"expectedVersion": str(version)},
    )

    assert res.status_code == 422
    assert res.json()["code"] == "UML_INVALID_MODEL"

    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["version"] == version


def test_image_command_batch_is_all_or_nothing_on_bad_relation_reference(client: TestClient):
    """
    Mismo criterio de atomicidad que CU6 texto: si la respuesta post-procesada
    de la imagen referencia una clase inexistente, no se crea NINGUNA clase del
    lote, ni siquiera las que sí resolvían bien antes de la relación rota.
    """
    canvas_id, version = _create_canvas(client)

    broken_result = {
        "classes": [{"id": "c1", "name": "Usuario", "attributes": [], "methods": []}],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c-inexistente",
                "labels": ["1", "1"],
            }
        ],
    }

    with patch(
        "backend_case.app.assistant.api.routes.call_gemini_from_image",
        return_value=broken_result,
    ):
        res = client.post(
            f"/api/v2/canvases/{canvas_id}/assistant/image-command",
            files={"image": ("diagrama.png", io.BytesIO(DUMMY_PNG), "image/png")},
            data={"expectedVersion": str(version)},
        )

    assert res.status_code == 422
    persisted = client.get(f"/api/v2/canvases/{canvas_id}").json()
    assert persisted["model"]["classes"] == []
    assert persisted["version"] == version
