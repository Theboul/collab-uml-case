import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend_case.app.main import app

client = TestClient(app)


def test_parity_ws_01_canvas_presence_and_broadcast():
    room = "test-room-1"

    # Peer 1 connects
    with client.websocket_connect(f"/ws/canvas/{room}/") as ws1:
        # Peer 1 receives join event for itself
        msg1 = ws1.receive_json()
        assert msg1["type"] == "presence"
        assert msg1["action"] == "join"
        peer1_id = msg1["peer"]

        # Peer 2 connects to same room
        with client.websocket_connect(f"/ws/canvas/{room}/") as ws2:
            # Peer 1 receives join event for peer 2
            peer2_join_for_peer1 = ws1.receive_json()
            assert peer2_join_for_peer1["type"] == "presence"
            assert peer2_join_for_peer1["action"] == "join"
            peer2_id = peer2_join_for_peer1["peer"]

            # Peer 2 receives its own join event
            peer2_join_for_peer2 = ws2.receive_json()
            assert peer2_join_for_peer2["type"] == "presence"
            assert peer2_join_for_peer2["action"] == "join"
            assert peer2_join_for_peer2["peer"] == peer2_id

            # Peer 1 broadcasts a state change
            payload = {"action": "move_node", "nodeId": "123", "x": 100, "y": 200}
            ws1.send_json({"type": "broadcast", "payload": payload})

            # Both peers receive the broadcast
            bcast_for_peer1 = ws1.receive_json()
            assert bcast_for_peer1["type"] == "broadcast"
            assert bcast_for_peer1["from"] == peer1_id
            assert bcast_for_peer1["payload"] == payload

            bcast_for_peer2 = ws2.receive_json()
            assert bcast_for_peer2["type"] == "broadcast"
            assert bcast_for_peer2["from"] == peer1_id
            assert bcast_for_peer2["payload"] == payload

            # Peer 2 sends direct WebRTC signal to Peer 1
            signal_payload = {"sdp": "dummy_offer_data"}
            ws2.send_json({"type": "signal", "to": peer1_id, "payload": signal_payload})

            # Only Peer 1 receives the direct signal
            sig_for_peer1 = ws1.receive_json()
            assert sig_for_peer1["type"] == "signal"
            assert sig_for_peer1["from"] == peer2_id
            assert sig_for_peer1["payload"] == signal_payload

        # Peer 2 disconnects -> Peer 1 receives leave event
        leave_msg = ws1.receive_json()
        assert leave_msg["type"] == "presence"
        assert leave_msg["action"] == "leave"
        assert leave_msg["peer"] == peer2_id


def test_parity_ws_05_uml_validation():
    mock_analysis = {
        "validas": [
            {"relacion": "association entre Cliente y Pedido", "razon": "Consistente con los atributos"}
        ],
        "errores": []
    }

    with patch("backend_case.app.legacy.ws_router.call_gemini_analysis", return_value=f"```json\n{json.dumps(mock_analysis)}\n```"):
        with client.websocket_connect("/ws/uml/") as ws:
            sample_uml = {
                "classes": [
                    {"id": "1", "name": "Cliente"},
                    {"id": "2", "name": "Pedido"}
                ],
                "relationships": [
                    {"id": "r1", "type": "association", "sourceId": "1", "targetId": "2"}
                ]
            }

            ws.send_json({
                "action": "validate_model",
                "uml": sample_uml
            })

            response = ws.receive_json()
            assert response["action"] == "validation_result"
            assert "analysis" in response
            assert response["analysis"]["validas"][0]["relacion"] == "association entre Cliente y Pedido"


@pytest.mark.anyio
async def test_parity_ws_redis_multi_process_coordination():
    from unittest.mock import AsyncMock, MagicMock

    from backend_case.app.legacy.signaling_manager import SignalingManager

    manager = SignalingManager()
    mock_redis = MagicMock()
    mock_redis.publish = AsyncMock()
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_redis.pubsub.return_value = mock_pubsub

    manager.redis_client = mock_redis
    manager.pubsub = mock_pubsub

    # Mock a local websocket connected in worker A
    mock_ws = AsyncMock()
    room = "collaborative-room-xyz"
    peer_a = "specific.peerA1234567"
    manager.rooms[room] = {peer_a: mock_ws}

    # 1. Action initiated on this worker: broadcast message
    await manager.handle_message(
        room_name=room,
        sender_peer_id=peer_a,
        data={"type": "broadcast", "payload": {"action": "create_node", "name": "Usuario"}},
    )

    # Verify message was published to Redis channel for multi-worker delivery
    assert mock_redis.publish.called
    channel_called, payload_called = mock_redis.publish.call_args[0]
    assert channel_called == f"canvas_room_{room}"
    published_event = json.loads(payload_called)
    assert published_event["event_type"] == "broadcast"
    assert published_event["from"] == peer_a
    assert published_event["payload"]["name"] == "Usuario"

    # 2. Incoming message from Redis (emitted by worker B in another process/container)
    event_from_worker_b = {
        "event_type": "broadcast",
        "room_name": room,
        "from": "specific.peerB9876543",
        "payload": {"action": "move_node", "x": 50, "y": 80},
    }
    await manager._dispatch_local(event_from_worker_b)

    # Verify local websocket received the message from worker B
    assert mock_ws.send_text.called
    local_delivered = json.loads(mock_ws.send_text.call_args[0][0])
    assert local_delivered["type"] == "broadcast"
    assert local_delivered["from"] == "specific.peerB9876543"
    assert local_delivered["payload"]["x"] == 50

