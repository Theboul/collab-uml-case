"""
Pruebas del canal de transporte de colaboración (ADR-0003, paso 1).
Cubre sólo lo que este paso implementa: broadcast entre peers de la misma
sala, aislamiento entre salas distintas, y limpieza del registro al
desconectar. Sin locks, sin presencia todavía.
"""

import asyncio
from unittest.mock import AsyncMock

from backend_case.app.collaboration.room_registry import (
    CollaborationRoomRegistry,
    ConnectedPeer,
    collaboration_room_registry,
)
from backend_case.app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_broadcast_reaches_other_peers_in_same_room_not_the_sender():
    # Lienzo real sin autenticación (owner_id=None -> ANFITRION para cualquiera,
    # ver resolver_rol): el WS ahora exige que el canvas_id exista y resuelva un
    # rol de edición antes de aceptar el handshake.
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Broadcast Test"}).json()["id"]

    with (
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws1,
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
    ):
        ws1.receive_json()  # handshake "connected" propio, no es el broadcast
        ws2.receive_json()

        payload = {"action": "move_node", "nodeId": "n1", "x": 10, "y": 20}
        ws1.send_json(payload)

        received = ws2.receive_json()
        assert received["payload"] == payload
        assert isinstance(received["from"], str) and received["from"]

        # El emisor no debe recibir su propio mensaje de vuelta.
        ws1.send_json({"action": "ping"})
        received_2 = ws2.receive_json()
        assert received_2["payload"] == {"action": "ping"}


def test_broadcast_includes_sender_display_name_end_to_end():
    """
    ADR-0003 paso 2: el frontend necesita el display_name del emisor para
    poder pintar su nombre junto al cursor remoto. Verifica que viaja por el
    envelope real (no sólo que quede guardado en el registro interno).
    """
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS DisplayName Test"}).json()["id"]

    with (
        client.websocket_connect(
            f"/ws/canvas/{canvas_id}/collaboration?display_name=Ana"
        ) as ws1,
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
    ):
        ws1.receive_json()  # handshake "connected" propio, no es el broadcast
        ws2.receive_json()

        ws1.send_json({"type": "cursor", "x": 10, "y": 20})
        received = ws2.receive_json()
        assert received["fromDisplayName"] == "Ana"

        # El peer sin display_name manda None, no revienta ni inventa un nombre.
        ws2.send_json({"type": "cursor", "x": 1, "y": 2})
        received_back = ws1.receive_json()
        assert received_back["fromDisplayName"] is None


def test_peers_in_different_canvas_are_registered_in_separate_rooms():
    # receive_json() bloquea indefinidamente si no llega nada, así que probar
    # "ws_b no recibe nada de la sala A" por WS sería un test que puede
    # colgarse. En su lugar verificamos el aislamiento donde es determinista:
    # el estado del registro, más el broadcast intra-sala (ya cubierto arriba).
    canvas_a = client.post("/api/v2/canvases", json={"name": "WS Room A"}).json()["id"]
    canvas_b = client.post("/api/v2/canvases", json={"name": "WS Room B"}).json()["id"]

    with (
        client.websocket_connect(f"/ws/canvas/{canvas_a}/collaboration"),
        client.websocket_connect(f"/ws/canvas/{canvas_b}/collaboration"),
    ):
        rooms = collaboration_room_registry.rooms
        assert canvas_a in rooms and canvas_b in rooms
        assert set(rooms[canvas_a].keys()).isdisjoint(rooms[canvas_b].keys())
        assert len(rooms[canvas_a]) == 1
        assert len(rooms[canvas_b]) == 1


def test_display_name_is_stored_on_connect():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS DisplayName Stored"}).json()["id"]

    with client.websocket_connect(
        f"/ws/canvas/{canvas_id}/collaboration?display_name=Ana"
    ):
        room = collaboration_room_registry.rooms.get(canvas_id, {})
        assert len(room) == 1
        peer = next(iter(room.values()))
        assert peer.display_name == "Ana"

    # Al salir del context manager el cliente cierra la conexión; el server
    # debe limpiar el registro.
    assert canvas_id not in collaboration_room_registry.rooms


def test_disconnect_removes_peer_from_registry():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Disconnect Test"}).json()["id"]

    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
        assert len(collaboration_room_registry.rooms.get(canvas_id, {})) == 1

        with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
            assert len(collaboration_room_registry.rooms.get(canvas_id, {})) == 2

        # El peer anidado salió del `with` (desconectado): el registro debe reflejarlo.
        assert len(collaboration_room_registry.rooms.get(canvas_id, {})) == 1

    assert canvas_id not in collaboration_room_registry.rooms


def test_disconnect_is_safe_after_broadcast_already_removed_the_peer():
    """
    Reproduce el caso puntual: broadcast() detecta un send_text() fallido y ya
    removió al peer del registro por su cuenta; el loop del router, al notar
    la misma desconexión por su lado, llama disconnect() para ese mismo
    peer_id. disconnect() debe ser un no-op seguro (sin excepción) tanto la
    primera vez (peer ya ausente) como si se lo llama dos veces seguidas.
    Va directo contra CollaborationRoomRegistry (no contra el WS real) para
    poder forzar de forma determinística el send_text() fallido.
    """

    async def _run() -> None:
        registry = CollaborationRoomRegistry()
        canvas_id = "canvas-collab-race"

        alive_ws = AsyncMock()
        dead_ws = AsyncMock()
        dead_ws.send_text.side_effect = RuntimeError("connection already closed")

        registry.rooms[canvas_id] = {
            "peer-alive": ConnectedPeer(websocket=alive_ws),
            "peer-dead": ConnectedPeer(websocket=dead_ws),
        }

        # peer-alive hace broadcast; el intento de mandarle a peer-dead falla,
        # así que broadcast() ya lo remueve del registro por su cuenta.
        await registry.broadcast(canvas_id, "peer-alive", {"action": "ping"})
        assert "peer-dead" not in registry.rooms[canvas_id]

        # El propio loop de peer-dead nota la desconexión y llama disconnect()
        # para un peer_id que broadcast() ya había sacado del registro.
        await registry.disconnect(canvas_id, "peer-dead")  # no debe lanzar

        # Llamarlo una segunda vez (ej. WebSocketDisconnect y luego el except
        # Exception genérico del router, o cualquier doble notificación) debe
        # seguir siendo inofensivo.
        await registry.disconnect(canvas_id, "peer-dead")

        # peer-alive sigue ahí; la sala no se borró de más.
        assert canvas_id in registry.rooms
        assert set(registry.rooms[canvas_id].keys()) == {"peer-alive"}

    asyncio.run(_run())


def test_disconnect_is_safe_when_it_was_the_last_peer_and_gets_called_twice():
    """
    Mismo caso pero cuando el peer muerto era el único en la sala: la primera
    llamada a disconnect() debe limpiar también la entrada `canvas_id` de
    `rooms` (queda vacía), y la segunda llamada debe seguir siendo un no-op
    aunque `canvas_id` ya ni siquiera esté en el registro.
    """

    async def _run() -> None:
        registry = CollaborationRoomRegistry()
        canvas_id = "canvas-collab-race-solo"

        registry.rooms[canvas_id] = {"peer-solo": ConnectedPeer(websocket=AsyncMock())}

        await registry.disconnect(canvas_id, "peer-solo")
        assert canvas_id not in registry.rooms

        await registry.disconnect(canvas_id, "peer-solo")  # no debe lanzar
        assert canvas_id not in registry.rooms

    asyncio.run(_run())


def test_connect_sends_peer_id_handshake():
    """El cliente necesita su propio peer_id para poder excluirse del broadcast
    de sus propios canvas_update (ver EditorCommandService/routes.py)."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Handshake Test"}).json()["id"]

    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws:
        handshake = ws.receive_json()
        assert handshake["type"] == "connected"
        assert isinstance(handshake["peerId"], str) and handshake["peerId"]


def test_http_command_broadcast_excludes_sender_via_peer_id():
    """
    Reproduce el escenario real: un comando ejecutado por HTTP con el peerId
    de la conexión WS activa del emisor no debe hacerle eco a ese mismo peer,
    pero sí debe llegar a los demás en la sala.
    """
    from backend_case.app.main import app as _app
    from fastapi.testclient import TestClient as _TestClient

    with _TestClient(_app) as scoped_client:
        canvas_id = scoped_client.post(
            "/api/v2/canvases", json={"name": "Lienzo Colab Peer"}
        ).json()["id"]

        with (
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws1,
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
        ):
            ws1_peer_id = ws1.receive_json()["peerId"]
            ws2.receive_json()

            cmd_res = scoped_client.post(
                f"/api/v2/canvases/{canvas_id}/commands",
                json={
                    "expectedVersion": 1,
                    "type": "CREATE_CLASS",
                    "payload": {"name": "Cliente", "x": 0, "y": 0, "width": 180, "height": 100},
                    "peerId": ws1_peer_id,
                },
            )
            assert cmd_res.status_code == 200

            received = ws2.receive_json()
            assert received["payload"]["type"] == "canvas_update"
            assert received["from"] == ws1_peer_id


def _register_and_get_token(client_: TestClient, email_prefix: str) -> str:
    """El sufijo uuid evita choques de email si el archivo SQLite persiste entre corridas."""
    import uuid as _uuid

    email = f"{email_prefix}-{_uuid.uuid4().hex[:8]}@schemacraft.dev"
    res = client_.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": "Test User"},
    )
    assert res.status_code == 201, res.text
    return res.json()["accessToken"]


def test_ws_rejects_connection_without_valid_role():
    """
    Hallazgo #1 de la auditoría: el WS de colaboración no validaba rol alguno.
    Sin token, o con el token de un usuario ajeno al lienzo, la conexión debe
    cerrarse con el código 4403 antes de entrar a la sala — nunca se le asigna
    peer_id ni queda registrada en collaboration_room_registry.
    """
    import pytest
    from backend_case.app.main import app as _app
    from starlette.websockets import WebSocketDisconnect

    with TestClient(_app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-403")
        outsider_token = _register_and_get_token(scoped_client, "outsider-ws-403")

        canvas_res = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Privado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        canvas_id = canvas_res.json()["id"]

        # Sin ningún token -> rechazado
        with (
            pytest.raises(WebSocketDisconnect) as exc_no_token,
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"),
        ):
            pass
        assert exc_no_token.value.code == 4403

        # Con token de un usuario autenticado pero ajeno al lienzo -> también rechazado
        with (
            pytest.raises(WebSocketDisconnect) as exc_outsider,
            scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration?token={outsider_token}"
            ),
        ):
            pass
        assert exc_outsider.value.code == 4403

        assert canvas_id not in collaboration_room_registry.rooms


def test_ws_accepts_connection_for_owner_and_joined_collaborator():
    """Contraparte del test anterior: el fix no debe romper el flujo legítimo."""
    from backend_case.app.main import app as _app

    with TestClient(_app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-ok")
        collab_token = _register_and_get_token(scoped_client, "collab-ws-ok")

        canvas_res = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Colaborativo"},
            headers={"Authorization": f"Bearer {owner_token}"},
        )
        canvas_id = canvas_res.json()["id"]
        room_name = canvas_res.json()["roomName"]

        join_res = scoped_client.post(
            "/api/v2/canvases/join",
            json={"accessCode": room_name},
            headers={"Authorization": f"Bearer {collab_token}"},
        )
        assert join_res.status_code == 200

        with scoped_client.websocket_connect(
            f"/ws/canvas/{canvas_id}/collaboration?token={owner_token}"
        ) as owner_ws:
            handshake = owner_ws.receive_json()
            assert handshake["type"] == "connected"

            with scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration?token={collab_token}"
            ) as collab_ws:
                collab_handshake = collab_ws.receive_json()
                assert collab_handshake["type"] == "connected"
                assert len(collaboration_room_registry.rooms.get(canvas_id, {})) == 2
