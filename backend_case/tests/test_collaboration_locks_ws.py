"""
Pruebas de integración del protocolo WebSocket para locks y presencia (Paso 5b, ADR-0003).

Cubre:
- Adquisición y renovación de locks entre múltiples sockets.
- Rechazo directo con reason='held' si otro peer lo posee.
- Límite de 20 locks por sesión con reason='limit'.
- Liberación explícita (lock_release).
- Ajuste B: titular recibe eco de su lock_acquired con holder.sessionId para evitar auto-bloqueo.
- Ajuste A: borrado de elemento por comando HTTP libera el lock y difunde lock_released.
- Snapshots al unirse (locks_snapshot y presence_snapshot).
- Desconexión: liberación automática de todos los locks y presence_left.
- Decisión 1: display_name proviene de la autenticación en el servidor (UserORM).
"""

import uuid

from fastapi.testclient import TestClient

from backend_case.app.collaboration.application.ports.lock_store import MAX_LOCKS_PER_SESSION
from backend_case.app.main import app

client = TestClient(app)


def _url(canvas_id: str) -> str:
    return f"/ws/canvas/{canvas_id}/collaboration"


def _register_user(client_: TestClient, email_prefix: str, full_name: str) -> str:
    unique_id = uuid.uuid4().hex[:8]
    email = f"{email_prefix}-{unique_id}@schemacraft.dev"
    res = client_.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": full_name},
    )
    assert res.status_code == 201, res.text
    return res.json()["accessToken"]


def _drain_connect(ws) -> dict:
    """Consume connected, locks_snapshot, presence_snapshot y devuelve el handshake connected."""
    conn = ws.receive_json()
    assert conn["type"] == "connected"
    locks = ws.receive_json()
    assert locks["type"] == "locks_snapshot"
    presence = ws.receive_json()
    assert presence["type"] == "presence_snapshot"
    return conn


def test_lock_acquire_and_denied_held_between_two_sockets():
    """
    Un peer adquiere un lock sobre elem1; el otro intenta adquirirlo y recibe
    lock_denied directo con reason='held' y el holder actual.
    """
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Lock Acquire"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as ws1,
        client.websocket_connect(_url(canvas_id)) as ws2,
    ):
        conn1 = _drain_connect(ws1)
        _drain_connect(ws2)
        # ws1 recibe presence_joined de ws2
        ws1.receive_json()

        # ws1 adquiere elem1
        ws1.send_json({"type": "lock_acquire", "elementId": "elem1"})

        # Ajuste B: ws1 recibe su propio lock_acquired
        echo1 = ws1.receive_json()
        assert echo1["payload"]["type"] == "lock_acquired"
        assert echo1["payload"]["elementId"] == "elem1"
        assert echo1["payload"]["holder"]["sessionId"] == conn1["peerId"]
        assert echo1["payload"]["ttlMs"] == 15000

        # ws2 recibe lock_acquired de la sala
        broadcast2 = ws2.receive_json()
        assert broadcast2["payload"]["type"] == "lock_acquired"
        assert broadcast2["payload"]["elementId"] == "elem1"
        assert broadcast2["payload"]["holder"]["sessionId"] == conn1["peerId"]

        # ws2 intenta adquirir el mismo elemento -> denegado directo
        ws2.send_json({"type": "lock_acquire", "elementId": "elem1"})
        denied = ws2.receive_json()
        # Directo: sin sobre {from, payload}
        assert denied["type"] == "lock_denied"
        assert denied["elementId"] == "elem1"
        assert denied["reason"] == "held"
        assert denied["holder"]["sessionId"] == conn1["peerId"]

        # ws1 NO recibe lock_denied (fue mensaje directo a ws2)
        ws1.send_json({"type": "cursor", "x": 10.0, "y": 20.0})
        cursor_msg = ws2.receive_json()
        assert cursor_msg["payload"]["type"] == "cursor"


def test_lock_renewal_is_idempotent_for_same_holder():
    """Renovar un lock antes de su expiración vuelve a emitir lock_acquired a la sala."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Lock Renew"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as ws1,
        client.websocket_connect(_url(canvas_id)) as ws2,
    ):
        _drain_connect(ws1)
        _drain_connect(ws2)
        ws1.receive_json()  # presence_joined de ws2

        ws1.send_json({"type": "lock_acquire", "elementId": "elem_renew"})
        ws1.receive_json()  # echo
        ws2.receive_json()  # broadcast

        # Renovar
        ws1.send_json({"type": "lock_acquire", "elementId": "elem_renew"})
        echo_renew = ws1.receive_json()
        assert echo_renew["payload"]["type"] == "lock_acquired"
        assert echo_renew["payload"]["elementId"] == "elem_renew"

        bcast_renew = ws2.receive_json()
        assert bcast_renew["payload"]["type"] == "lock_acquired"
        assert bcast_renew["payload"]["elementId"] == "elem_renew"


def test_lock_cap_limit_20_locks_returns_limit_reason():
    """Superar el tope de 20 locks por sesión devuelve lock_denied con reason='limit'."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Lock Limit"}).json()["id"]

    with client.websocket_connect(_url(canvas_id)) as ws:
        _drain_connect(ws)

        for i in range(MAX_LOCKS_PER_SESSION):
            ws.send_json({"type": "lock_acquire", "elementId": f"elem_{i}"})
            res = ws.receive_json()
            assert res["payload"]["type"] == "lock_acquired"

        # Intento número 21 -> denegado por límite
        ws.send_json({"type": "lock_acquire", "elementId": "elem_overflow"})
        denied = ws.receive_json()
        assert denied["type"] == "lock_denied"
        assert denied["elementId"] == "elem_overflow"
        assert denied["reason"] == "limit"
        assert denied["holder"] is None


def test_lock_release_frees_element_and_broadcasts_to_room():
    """
    lock_release libera el lock y emite lock_released a los demás;
    luego otro peer puede tomarlo.
    """
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Lock Release"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as ws1,
        client.websocket_connect(_url(canvas_id)) as ws2,
    ):
        _drain_connect(ws1)
        conn2 = _drain_connect(ws2)
        ws1.receive_json()  # presence_joined

        # ws1 adquiere y luego libera
        ws1.send_json({"type": "lock_acquire", "elementId": "elem_rel"})
        ws1.receive_json()  # echo ws1
        ws2.receive_json()  # bcast ws2

        ws1.send_json({"type": "lock_release", "elementId": "elem_rel"})
        rel_bcast = ws2.receive_json()
        assert rel_bcast["payload"]["type"] == "lock_released"
        assert rel_bcast["payload"]["elementId"] == "elem_rel"

        # Ahora ws2 puede adquirirlo
        ws2.send_json({"type": "lock_acquire", "elementId": "elem_rel"})
        echo_ws2 = ws2.receive_json()
        assert echo_ws2["payload"]["type"] == "lock_acquired"
        assert echo_ws2["payload"]["holder"]["sessionId"] == conn2["peerId"]


def test_snapshots_on_join_contain_existing_locks_and_presence():
    """Al unirse, una sesión recibe locks_snapshot con los locks activos y presence_snapshot."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Snapshots"}).json()["id"]

    with client.websocket_connect(_url(canvas_id)) as ws1:
        conn1 = _drain_connect(ws1)

        ws1.send_json({"type": "lock_acquire", "elementId": "box_a"})
        ws1.receive_json()
        ws1.send_json({"type": "lock_acquire", "elementId": "box_b"})
        ws1.receive_json()

        # ws2 se une ahora: debe recibir en su handshake los locks de ws1 y la presencia
        with client.websocket_connect(_url(canvas_id)) as ws2:
            conn2 = ws2.receive_json()
            assert conn2["type"] == "connected"

            locks_msg = ws2.receive_json()
            assert locks_msg["type"] == "locks_snapshot"
            locked_ids = {item["elementId"] for item in locks_msg["locks"]}
            assert locked_ids == {"box_a", "box_b"}
            for lock_item in locks_msg["locks"]:
                assert lock_item["holder"]["sessionId"] == conn1["peerId"]
                assert lock_item["ttlMs"] == 15000

            presence_msg = ws2.receive_json()
            assert presence_msg["type"] == "presence_snapshot"
            session_ids = {s["sessionId"] for s in presence_msg["sessions"]}
            assert conn1["peerId"] in session_ids
            assert conn2["peerId"] in session_ids


def test_disconnect_releases_all_held_locks_and_emits_presence_left():
    """Al desconectarse un socket, todos sus locks se liberan y se emite presence_left."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Disconnect Clean"}).json()["id"]

    with client.websocket_connect(_url(canvas_id)) as ws2:
        _drain_connect(ws2)

        with client.websocket_connect(_url(canvas_id)) as ws1:
            conn1 = _drain_connect(ws1)
            ws2.receive_json()  # presence_joined de ws1

            ws1.send_json({"type": "lock_acquire", "elementId": "elem_x"})
            ws1.receive_json()
            ws2.receive_json()
            ws1.send_json({"type": "lock_acquire", "elementId": "elem_y"})
            ws1.receive_json()
            ws2.receive_json()

        # ws1 salió: ws2 debe recibir lock_released por elem_x, elem_y y presence_left
        msg_a = ws2.receive_json()
        msg_b = ws2.receive_json()
        msg_c = ws2.receive_json()

        received_types = [m["payload"]["type"] for m in (msg_a, msg_b, msg_c)]
        assert received_types.count("lock_released") == 2
        assert received_types.count("presence_left") == 1

        released_ids = {
            m["payload"]["elementId"]
            for m in (msg_a, msg_b, msg_c)
            if m["payload"]["type"] == "lock_released"
        }
        assert released_ids == {"elem_x", "elem_y"}

        left_msg = next(m for m in (msg_a, msg_b, msg_c) if m["payload"]["type"] == "presence_left")
        assert left_msg["payload"]["sessionId"] == conn1["peerId"]


def test_ajuste_a_delete_element_releases_lock_and_broadcasts():
    """
    Ajuste A: Cuando un elemento se borra por comando HTTP, se libera su lock de inmediato
    y se publica lock_released a la sala.
    """
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Delete Lock"}).json()["id"]

    # Crear una clase
    base = f"/api/v2/canvases/{canvas_id}"
    created_class = client.post(f"{base}/classes", json={"name": "Persona"})
    assert created_class.status_code == 201
    class_id = created_class.json()["model"]["classes"][0]["id"]

    with client.websocket_connect(_url(canvas_id)) as ws:
        _drain_connect(ws)

        # Adquirir lock sobre la clase
        ws.send_json({"type": "lock_acquire", "elementId": class_id})
        echo = ws.receive_json()
        assert echo["payload"]["type"] == "lock_acquired"

        # Borrar la clase por comando HTTP
        cmd_res = client.post(
            f"{base}/commands",
            json={
                "expectedVersion": 2,
                "type": "DELETE_CLASS",
                "payload": {"classId": class_id},
            },
        )
        assert cmd_res.status_code == 200

        # El websocket debe recibir el canvas_delta y el lock_released
        msg1 = ws.receive_json()
        msg2 = ws.receive_json()

        types = {msg1["payload"]["type"], msg2["payload"]["type"]}
        assert "canvas_delta" in types
        assert "lock_released" in types

        rel_msg = msg1 if msg1["payload"]["type"] == "lock_released" else msg2
        assert rel_msg["payload"]["elementId"] == class_id


def test_decision_1_authenticated_user_display_name_in_locks_and_presence():
    """
    Decisión 1: display_name proviene siempre del usuario autenticado en BD (UserORM),
    no del parámetro de URL ?display_name=.
    """
    token_carlos = _register_user(client, "carlos_auth", full_name="Carlos Garcia")
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Auth DisplayName"}).json()["id"]

    with (
        client.websocket_connect(
            f"{_url(canvas_id)}?display_name=Impostor",
            subprotocols=["bearer", token_carlos],
        ) as ws1,
        client.websocket_connect(_url(canvas_id)) as ws2,
    ):
        _drain_connect(ws1)
        _drain_connect(ws2)

        # ws1 recibe presence_joined de ws2
        ws1.receive_json()

        # ws1 adquiere un lock
        ws1.send_json({"type": "lock_acquire", "elementId": "box_auth"})
        echo = ws1.receive_json()
        assert echo["payload"]["holder"]["displayName"] == "Carlos Garcia"

        # ws2 ve el lock con el nombre auténtico
        bcast = ws2.receive_json()
        assert bcast["payload"]["holder"]["displayName"] == "Carlos Garcia"
