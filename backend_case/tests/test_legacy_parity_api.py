import asyncio
import io
import json
import uuid
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.legacy.database import init_legacy_db
from backend_case.app.main import app
from backend_case.app.shared.db.base import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def ensure_db():
    asyncio.run(init_legacy_db())
    asyncio.run(init_db())  # tablas del backend nuevo: el registro de usuarios las necesita


@pytest.fixture(autouse=True)
def sesion_autenticada(ensure_db):
    """La API legacy exige Access Token: `client` va autenticado salvo en los tests sin token."""
    res = TestClient(app).post(
        "/api/v2/auth/register",
        json={
            "email": f"legacy-{uuid.uuid4().hex[:8]}@schemacraft.dev",
            "password": "Password123!",
            "fullName": "Legacy Test",
        },
    )
    assert res.status_code == 201, res.text
    client.headers["Authorization"] = f"Bearer {res.json()['accessToken']}"
    yield
    client.headers.pop("Authorization", None)


def test_parity_api_01_chatbot_success():
    mock_gemini_output = json.dumps({
        "classes": [
            {
                "id": "c1",
                "name": "Cliente",
                "attributes": [{"name": "id", "type": "int"}],
                "methods": []
            }
        ],
        "relationships": []
    })

    with patch("backend_case.app.legacy.api_router.call_gemini", return_value=f"```json\n{mock_gemini_output}\n```"):
        response = client.post("/api/chatbot/", json={"prompt": "Crea una clase Cliente"})
        assert response.status_code == 200
        data = response.json()
        assert "classes" in data
        assert len(data["classes"]) == 1
        assert data["classes"][0]["name"] == "Cliente"


def test_parity_api_02_chatbot_missing_prompt():
    response = client.post("/api/chatbot/", json={})
    assert response.status_code == 400
    assert response.json() == {"error": "El campo 'prompt' es requerido"}


def test_parity_api_03_04_05_06_backup_uml_lifecycle():
    room_id = str(uuid.uuid4())
    initial_uml = {
        "classes": [{"id": "c1", "name": "Usuario"}],
        "relationships": []
    }

    # 1. Get before creation -> 404
    get_res_empty = client.get(f"/api/get_backup_uml/{room_id}/")
    assert get_res_empty.status_code == 404
    assert get_res_empty.json() == {"error": "No existe un diagrama con ese ID"}

    # 2. Create -> 201
    set_res = client.post(f"/api/set_backup_uml/{room_id}/", json=initial_uml)
    assert set_res.status_code == 201
    set_data = set_res.json()
    assert set_data["message"] == "UML creado con éxito"
    assert set_data["room_id"] == room_id
    assert set_data["data"] == initial_uml

    # 3. Retrieve -> 200
    get_res = client.get(f"/api/get_backup_uml/{room_id}/")
    assert get_res.status_code == 200
    assert get_res.json() == initial_uml

    # 4. Update -> 200
    updated_uml = {
        "classes": [
            {"id": "c1", "name": "Usuario"},
            {"id": "c2", "name": "Perfil"}
        ],
        "relationships": []
    }
    update_res = client.post(f"/api/set_backup_uml/{room_id}/", json=updated_uml)
    assert update_res.status_code == 200
    update_data = update_res.json()
    assert update_data["message"] == "UML actualizado con éxito"
    assert update_data["room_id"] == room_id
    assert update_data["data"] == updated_uml

    # 5. Retrieve updated -> 200
    get_res2 = client.get(f"/api/get_backup_uml/{room_id}/")
    assert get_res2.status_code == 200
    assert len(get_res2.json()["classes"]) == 2


def test_parity_api_07_uml_from_image():
    mock_processed_result = {
        "classes": [{"id": "c1", "name": "Producto", "attributes": [], "methods": []}],
        "relationships": []
    }

    with patch("backend_case.app.legacy.api_router.call_gemini_from_image", return_value=mock_processed_result):
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"image": ("test.png", io.BytesIO(dummy_png), "image/png")}
        response = client.post("/api/uml_from_image/", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "uml_json" in data
        assert data["uml_json"]["classes"][0]["name"] == "Producto"


def test_parity_api_07b_uml_from_image_never_leaks_gemini_error_detail():
    """
    call_gemini_from_image atrapa sus propias excepciones y devuelve
    {"error": str(e)} -- para errores HTTP de `requests`, ese string incluye
    la URL completa de la request, con la API key de Gemini en el query
    string. El valor de la key acá es sintético (no una key real, ni siquiera
    una ya rotada) -- alcanza con probar que CUALQUIER string con esa forma
    nunca llega al cliente, sin dejar un fragmento de credencial real en el
    repo.
    """
    leaky_detail = (
        "400 Client Error: Bad Request for url: "
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-flash-lite-latest:generateContent?key=AQ.FakeSyntheticKeyForTestingOnly123"
    )

    with patch(
        "backend_case.app.legacy.api_router.call_gemini_from_image",
        return_value={"error": leaky_detail},
    ):
        dummy_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
        files = {"image": ("borrosa.png", io.BytesIO(dummy_png), "image/png")}
        response = client.post("/api/uml_from_image/", files=files)

    assert response.status_code == 200
    body_text = response.text
    assert "key=" not in body_text
    assert "FakeSyntheticKeyForTestingOnly123" not in body_text
    assert "generativelanguage.googleapis.com" not in body_text
    assert "No se pudo interpretar la imagen" in body_text


def test_parity_api_08_generar_flutter_success():
    valid_uml = {
        "classes": [
            {
                "id": "c1",
                "name": "Cliente",
                "attributes": [
                    {"name": "id", "type": "int"},
                    {"name": "nombre", "type": "string"}
                ],
                "methods": []
            }
        ],
        "relationships": []
    }

    response = client.post("/api/generar_flutter/", json=valid_uml)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "attachment; filename=\"flutter_project.zip\"" in response.headers.get("content-disposition", "")

    # Validate that it is a valid zip archive
    zip_bytes = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_bytes, "r") as zf:
        namelist = zf.namelist()
        assert any("pubspec.yaml" in name for name in namelist)
        assert any("lib/main.dart" in name for name in namelist)


def test_parity_api_09_generar_flutter_missing_classes():
    invalid_uml = {"relationships": []}
    response = client.post("/api/generar_flutter/", json=invalid_uml)
    assert response.status_code == 400
    assert response.json() == {"error": "El JSON UML debe contener 'classes'."}


RUTAS_LEGACY = [
    ("post", "/api/chatbot/"),
    ("post", "/api/set_backup_uml/sala-1/"),
    ("get", "/api/get_backup_uml/sala-1/"),
    ("post", "/api/uml_from_image/"),
    ("post", "/api/generar_flutter/"),
]


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_LEGACY)
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer no-es-un-jwt"}])
def test_legacy_api_sin_token_valido_responde_401(metodo, ruta, headers):
    """Sin Access Token válido ninguna ruta legacy responde, y Gemini nunca se invoca."""
    with (
        patch("backend_case.app.legacy.api_router.call_gemini") as gemini,
        patch("backend_case.app.legacy.api_router.call_gemini_from_image") as gemini_imagen,
    ):
        respuesta = getattr(TestClient(app), metodo)(ruta, headers=headers)

    assert respuesta.status_code == 401
    assert "AUTH_" in respuesta.text
    gemini.assert_not_called()
    gemini_imagen.assert_not_called()
