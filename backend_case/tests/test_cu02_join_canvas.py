import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from backend_case.app.main import app
from backend_case.app.shared.db.base import init_db


@pytest.fixture(autouse=True)
async def ensure_db():
    await init_db()


async def _register_user(client: AsyncClient, email_prefix: str) -> str:
    """Registra un usuario nuevo con email único y devuelve su accessToken."""
    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@schemacraft.dev"
    res = await client.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": "Test User"},
    )
    assert res.status_code == 201, res.text
    return res.json()["accessToken"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_join_canvas_with_valid_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_token = await _register_user(client, "owner-cu02")
        collaborator_token = await _register_user(client, "collaborator-cu02")

        # 1. Crear un lienzo inicial (CU1)
        create_res = await client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo de Prueba CU2", "description": "Para test de ingreso"},
            headers=_auth_headers(owner_token),
        )
        assert create_res.status_code == 201
        created = create_res.json()
        room_name = created["roomName"]
        canvas_id = created["id"]
        assert room_name is not None

        # 2. Unirse con el código exacto (usuario distinto al dueño)
        join_res = await client.post(
            "/api/v2/canvases/join",
            json={"accessCode": room_name},
            headers=_auth_headers(collaborator_token),
        )
        assert join_res.status_code == 200
        join_data = join_res.json()
        assert join_data["canvasId"] == canvas_id
        assert join_data["roomName"] == room_name
        assert join_data["role"] in ["COLABORADOR", "ANFITRION"]

        # 3. Unirse con código normalizado (sin prefijo 'room-' o con espacios)
        clean_code = room_name.replace("room-", "")
        join_res2 = await client.post(
            "/api/v2/canvases/join",
            json={"accessCode": f"  {clean_code.upper()}  "},
            headers=_auth_headers(collaborator_token),
        )
        assert join_res2.status_code == 200
        join_data2 = join_res2.json()
        assert join_data2["canvasId"] == canvas_id
        assert join_data2["joined"] is False  # Idempotente: no crea duplicado


@pytest.mark.anyio
async def test_join_canvas_invalid_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await _register_user(client, "solo-cu02-invalid-code")
        res = await client.post(
            "/api/v2/canvases/join",
            json={"accessCode": "codigo-que-no-existe-9999"},
            headers=_auth_headers(token),
        )
        assert res.status_code == 404
        data = res.json()
        assert data["code"] == "ACCESS_CODE_INVALID"


@pytest.mark.anyio
async def test_join_canvas_without_auth_is_rejected():
    """
    `canvas_collaborators.user_id` es FK NOT NULL contra `users.id` (parte de la PK
    compuesta): unirse sin sesión no puede persistir un colaborador real, así que la ruta
    debe exigir autenticación en vez de usar un id inventado (ver nota en join_canvas).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        owner_token = await _register_user(client, "owner-cu02-noauth")
        create_res = await client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo Sin Auth"},
            headers=_auth_headers(owner_token),
        )
        room_name = create_res.json()["roomName"]

        res = await client.post(
            "/api/v2/canvases/join",
            json={"accessCode": room_name},
        )
        assert res.status_code == 401
        assert res.json()["code"] == "AUTH_REQUIRED"


@pytest.mark.anyio
async def test_snapshot_retrieval_after_join():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Crear lienzo
        create_res = await client.post(
            "/api/v2/canvases",
            json={"name": "Diagrama Colaborativo"},
        )
        assert create_res.status_code == 201
        created = create_res.json()
        room_name = created["roomName"]
        canvas_id = created["id"]

        # Agregar clase para verificar recuperación exacta
        cmd_res = await client.post(
            f"/api/v2/canvases/{canvas_id}/commands",
            json={
                "expectedVersion": 1,
                "type": "CREATE_CLASS",
                "payload": {
                    "classId": "c-test-1",
                    "name": "Cliente",
                    "isAbstract": False,
                    "x": 200,
                    "y": 150,
                    "width": 190,
                    "height": 130,
                },
            },
        )
        assert cmd_res.status_code == 200

        # Recuperar snapshot por room_name
        snapshot_res = await client.get(f"/api/v2/canvases/by-room/{room_name}")
        assert snapshot_res.status_code == 200
        snapshot = snapshot_res.json()
        assert snapshot["name"] == "Diagrama Colaborativo"
        assert snapshot["version"] == 2
        assert len(snapshot["model"]["classes"]) == 1
        assert snapshot["model"]["classes"][0]["name"] == "Cliente"
        assert "c-test-1" in snapshot["visualLayout"]["nodes"]
        assert snapshot["visualLayout"]["nodes"]["c-test-1"]["x"] == 200
