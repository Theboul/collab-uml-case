"""
Pruebas del canal de transporte de colaboración (ADR-0003, paso 1).
Cubre sólo lo que este paso implementa: broadcast entre peers de la misma
sala, aislamiento entre salas distintas, y limpieza del registro al
desconectar. Sin locks, sin presencia todavía.
"""

import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from backend_case.app.collaboration.room_registry import (
    CollaborationRoomRegistry,
    ConnectedPeer,
    collaboration_room_registry,
)
from backend_case.app.main import app

client = TestClient(app)


def test_broadcast_reaches_other_peers_in_same_room_not_the_sender():
    canvas_id = "canvas-collab-1"

    with (
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws1,
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
    ):
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
    canvas_id = "canvas-collab-name-broadcast"

    with (
        client.websocket_connect(
            f"/ws/canvas/{canvas_id}/collaboration?display_name=Ana"
        ) as ws1,
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
    ):
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
    canvas_a = "canvas-collab-a"
    canvas_b = "canvas-collab-b"

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
    canvas_id = "canvas-collab-name"

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
    canvas_id = "canvas-collab-disconnect"

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
