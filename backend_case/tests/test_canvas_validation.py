"""
Pruebas para CU9 (Validar el modelo UML) conectado a un canvas real:
POST /api/v2/canvases/{canvas_id}/validate.

Nota: UMLValidator.validate() no emite ningún issue de severidad WARNING hoy
(solo SpringCompatibilityValidator/FlutterCompatibilityValidator lo hacen, y
ninguno de los dos participa de este endpoint) — por eso no hay un test de
"modelo con warning" acá; sería fabricar un caso que el motor real no produce.
"""

import pytest
from backend_case.app.main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _register_user(client: TestClient, email_prefix: str) -> str:
    """Registra un usuario nuevo con email único (uuid) y devuelve su accessToken."""
    import uuid as _uuid

    email = f"{email_prefix}-{_uuid.uuid4().hex[:8]}@schemacraft.dev"
    res = client.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": "Test User"},
    )
    assert res.status_code == 201, res.text
    return res.json()["accessToken"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_validate_canvas_valid_model(client: TestClient):
    """Un lienzo recién creado (sin clases) es válido: sin errores ni advertencias."""
    create_res = client.post("/api/v2/canvases", json={"name": "Lienzo Válido CU9"})
    canvas_id = create_res.json()["id"]

    res = client.post(f"/api/v2/canvases/{canvas_id}/validate")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["errors"] == []
    assert data["warnings"] == []


def test_validate_canvas_with_inheritance_cycle_error(client: TestClient):
    """
    A->B, B->C, C->A vía tres comandos CREATE_RELATION separados: cada uno es
    válido de forma aislada (CREATE_RELATION no chequea ciclos al crear una
    generalización individual, confirmado en class_handlers.py/relation_handlers.py),
    así que la única forma de detectar el ciclo resultante es la validación
    global de CU9 (VUML-07) — el caso real que demuestra por qué CU9 no es
    redundante con las validaciones locales de CU3/CU4.
    """
    create_res = client.post("/api/v2/canvases", json={"name": "Lienzo Con Ciclo CU9"})
    canvas_id = create_res.json()["id"]

    class_ids = {}
    for i, name in enumerate(["A", "B", "C"], start=1):
        cmd_res = client.post(
            f"/api/v2/canvases/{canvas_id}/commands",
            json={
                "expectedVersion": i,
                "type": "CREATE_CLASS",
                "payload": {"name": name, "x": 100 * i, "y": 100},
            },
        )
        classes = cmd_res.json()["canvas"]["model"]["classes"]
        class_ids[name] = next(c["id"] for c in classes if c["name"] == name)

    version = 4
    for source, target in [("A", "B"), ("B", "C"), ("C", "A")]:
        gen_res = client.post(
            f"/api/v2/canvases/{canvas_id}/commands",
            json={
                "expectedVersion": version,
                "type": "CREATE_RELATION",
                "payload": {
                    "sourceClassId": class_ids[source],
                    "targetClassId": class_ids[target],
                    "type": "GENERALIZATION",
                },
            },
        )
        assert gen_res.status_code == 200, gen_res.text
        version += 1

    res = client.post(f"/api/v2/canvases/{canvas_id}/validate")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is False
    assert any(err["code"] == "VUML-07" for err in data["errors"])
    assert data["warnings"] == []


def test_validate_canvas_not_found(client: TestClient):
    """Canvas inexistente: el exception handler global de dominio devuelve 404."""
    res = client.post("/api/v2/canvases/no-existe-este-id/validate")
    assert res.status_code == 404


def test_validate_canvas_forbidden_for_user_without_access(client: TestClient):
    """Mismo control de acceso que GET /{canvas_id}: un ajeno no puede validar un lienzo privado."""
    owner_token = _register_user(client, "owner-validate")
    outsider_token = _register_user(client, "outsider-validate")

    create_res = client.post(
        "/api/v2/canvases",
        json={"name": "Lienzo Privado Validar"},
        headers=_auth_headers(owner_token),
    )
    canvas_id = create_res.json()["id"]

    outsider_res = client.post(
        f"/api/v2/canvases/{canvas_id}/validate", headers=_auth_headers(outsider_token)
    )
    assert outsider_res.status_code == 403
    assert outsider_res.json()["code"] == "CANVAS_ACCESS_FORBIDDEN"

    owner_res = client.post(
        f"/api/v2/canvases/{canvas_id}/validate", headers=_auth_headers(owner_token)
    )
    assert owner_res.status_code == 200
    assert owner_res.json()["valid"] is True


def test_validate_canvas_does_not_mutate_model(client: TestClient):
    """Postcondición explícita del CU: validar no cambia el modelo ni su versión."""
    create_res = client.post("/api/v2/canvases", json={"name": "Lienzo Inmutable CU9"})
    canvas_id = create_res.json()["id"]
    version_antes = create_res.json()["version"]

    client.post(f"/api/v2/canvases/{canvas_id}/validate")
    client.post(f"/api/v2/canvases/{canvas_id}/validate")

    after_res = client.get(f"/api/v2/canvases/{canvas_id}")
    assert after_res.json()["version"] == version_antes
