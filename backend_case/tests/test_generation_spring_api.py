"""
Pruebas de integración de CU10: POST /api/v2/canvases/{id}/generation/spring.

El puerto SpringGeneratorPort (HttpSpringAdapter.generate) se mockea siempre
-- estas pruebas no dependen de que el generador Java real esté levantado.
Confirman: un modelo válido llega hasta el puerto y su .zip se devuelve tal
cual con Content-Disposition; un modelo con herencia múltiple (VGEN-SB-01,
SpringCompatibilityValidator) se rechaza con 4xx explícito ANTES de invocar
al puerto; y una falla de conexión/timeout del generador real nunca escapa
como 500 genérico.
"""

import io
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.generation.application.ports.spring_port import (
    SpringGeneratorUnavailableError,
)
from backend_case.app.generation.infrastructure.spring.http_spring_adapter import (
    HttpSpringAdapter,
)
from backend_case.app.main import app


def _build_fake_zip_bytes() -> bytes:
    """
    El puerto se mockea (no hay generador Java real en el test), pero el
    mock devuelve un .zip REAL y válido -- no un string cualquiera con el
    prefijo "PK". Esto es lo que permite al test abrir el zip y confirmar
    que no está corrupto, en vez de solo comparar bytes ciegamente.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("pom.xml", "<project>fake-pom</project>")
        zf.writestr("src/main/java/com/example/genapp/Application.java", "// fake entity")
    return buffer.getvalue()


FAKE_ZIP_BYTES = _build_fake_zip_bytes()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_canvas(client: TestClient, name: str) -> tuple[str, int]:
    res = client.post("/api/v2/canvases", json={"name": name})
    assert res.status_code == 201
    data = res.json()
    return data["id"], data["version"]


def _create_class(client: TestClient, canvas_id: str, version: int, name: str) -> tuple[str, int]:
    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_CLASS",
            "payload": {"name": name, "x": 100.0, "y": 100.0},
        },
    )
    assert res.status_code == 200, res.text
    classes = res.json()["canvas"]["model"]["classes"]
    class_id = next(c["id"] for c in classes if c["name"] == name)
    return class_id, version + 1


def _create_generalization(
    client: TestClient, canvas_id: str, version: int, source_id: str, target_id: str
) -> int:
    res = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "CREATE_RELATION",
            "payload": {
                "sourceClassId": source_id,
                "targetClassId": target_id,
                "type": "GENERALIZATION",
            },
        },
    )
    assert res.status_code == 200, res.text
    return version + 1


def test_generate_spring_backend_valid_model_returns_zip(client: TestClient):
    canvas_id, version = _create_canvas(client, "Lienzo CU10 Válido")
    class_id, version = _create_class(client, canvas_id, version, "Producto")

    res_attr = client.post(
        f"/api/v2/canvases/{canvas_id}/commands",
        json={
            "expectedVersion": version,
            "type": "ADD_ATTRIBUTE",
            "payload": {"classId": class_id, "name": "nombre", "type": "String"},
        },
    )
    assert res_attr.status_code == 200, res_attr.text

    with patch.object(HttpSpringAdapter, "generate", return_value=FAKE_ZIP_BYTES) as mock_generate:
        res = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert "attachment;" in res.headers.get("content-disposition", "")
    assert res.content == FAKE_ZIP_BYTES

    # No alcanza con comparar bytes: se abre el .zip devuelto y se confirma
    # que zipfile puede leerlo sin corrupción y que las entradas conocidas
    # están -- así un mock que devolviera basura con solo el prefijo "PK"
    # haría fallar el test, no solo uno que devuelva bytes distintos.
    with zipfile.ZipFile(io.BytesIO(res.content)) as zf:
        assert zf.testzip() is None
        namelist = zf.namelist()
        assert "pom.xml" in namelist
        assert "src/main/java/com/example/genapp/Application.java" in namelist

    # El payload enviado al puerto tiene la forma {classes, relationships} de
    # LegacyOutputAdapter.to_legacy_dto, la misma que espera UmlSchema (Java).
    sent_payload = mock_generate.call_args[0][0]
    assert {c["name"] for c in sent_payload["classes"]} == {"Producto"}
    assert sent_payload["relationships"] == []


def test_generate_spring_backend_rejects_multiple_inheritance_without_calling_port(
    client: TestClient,
):
    """
    VGEN-SB-01 (SpringCompatibilityValidator): una subclase con más de una
    generalización es incompatible con la generación de entidades Java
    estándar. Debe rechazarse con 4xx controlado -- y el puerto de generación
    NUNCA debe invocarse, confirmando que el rechazo ocurre antes de llamar
    al generador real.
    """
    canvas_id, version = _create_canvas(client, "Lienzo CU10 Herencia Múltiple")
    subclass_id, version = _create_class(client, canvas_id, version, "Empleado")
    super_a_id, version = _create_class(client, canvas_id, version, "Persona")
    super_b_id, version = _create_class(client, canvas_id, version, "Contribuyente")

    version = _create_generalization(client, canvas_id, version, subclass_id, super_a_id)
    version = _create_generalization(client, canvas_id, version, subclass_id, super_b_id)

    with patch.object(HttpSpringAdapter, "generate") as mock_generate:
        res = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")

    assert res.status_code < 500
    assert res.status_code == 400
    body = res.json()
    assert body["code"] == "UNSUPPORTED_GENERATION_FEATURE"
    assert "Empleado" in body["message"]
    mock_generate.assert_not_called()


def test_generate_spring_backend_generator_unavailable_returns_controlled_503(
    client: TestClient,
):
    """
    Si back_generator_uml está caído, en timeout, o inalcanzable,
    HttpSpringAdapter.generate traduce eso a SpringGeneratorUnavailableError -- el
    router lo traduce a un 503 explícito, nunca a un 500 genérico sin manejar.
    """
    canvas_id, version = _create_canvas(client, "Lienzo CU10 Generador Caído")
    _create_class(client, canvas_id, version, "Producto")

    with patch.object(
        HttpSpringAdapter,
        "generate",
        side_effect=SpringGeneratorUnavailableError(
            "No se pudo conectar con el generador de backend Spring Boot."
        ),
    ):
        res = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")

    assert res.status_code == 503
    assert res.json()["code"] == "SPRING_GENERATOR_UNAVAILABLE"


def test_generate_spring_backend_rejects_empty_model_without_calling_port(client: TestClient):
    """
    Precondición de CU10 ("modelo UML con información suficiente"): un lienzo sin
    ninguna clase se rechaza con 422 controlado ANTES de invocar al generador --
    no se entrega un zip ni una colección Postman vacíos.
    """
    canvas_id, _ = _create_canvas(client, "Lienzo CU10 Vacío")

    with patch.object(HttpSpringAdapter, "generate") as mock_generate:
        res = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")

    assert res.status_code == 422
    assert res.headers["content-type"] == "application/json"
    assert "content-disposition" not in res.headers
    body = res.json()
    assert body["code"] == "GENERATION_EMPTY_MODEL"
    assert "al menos una clase" in body["message"]
    assert body["details"] == []
    mock_generate.assert_not_called()


def test_generate_spring_backend_empty_model_check_lifts_once_a_class_exists(client: TestClient):
    canvas_id, version = _create_canvas(client, "Lienzo CU10 Vacío y luego con clase")

    with patch.object(HttpSpringAdapter, "generate", return_value=FAKE_ZIP_BYTES) as mock_generate:
        empty = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")
        assert empty.status_code == 422
        mock_generate.assert_not_called()

        _create_class(client, canvas_id, version, "Producto")
        filled = client.post(f"/api/v2/canvases/{canvas_id}/generation/spring")

    assert filled.status_code == 200
    assert filled.headers["content-type"] == "application/zip"
    mock_generate.assert_called_once()
