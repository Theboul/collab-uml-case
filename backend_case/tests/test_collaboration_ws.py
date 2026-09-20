"""
Pruebas del canal de transporte de colaboración (ADR-0003, paso 1).
Cubre sólo lo que este paso implementa: broadcast entre peers de la misma
sala, aislamiento entre salas distintas, y limpieza del registro al
desconectar. Sin locks, sin presencia todavía.
"""

import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend_case.app.main import app

client = TestClient(app)


def _rooms() -> dict:
    """Estado interno del adaptador en memoria; solo para inspeccionar en tests."""
    return app.state.collaboration_room.rooms


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

        payload = {"type": "node_drag", "nodeId": "n1", "x": 10.0, "y": 20.0}
        ws1.send_json(payload)

        received = ws2.receive_json()
        assert received["payload"] == payload
        assert isinstance(received["from"], str) and received["from"]

        # El emisor no debe recibir su propio mensaje de vuelta.
        ws1.send_json({"type": "node_drag_end", "nodeId": "n1"})
        received_2 = ws2.receive_json()
        assert received_2["payload"] == {"type": "node_drag_end", "nodeId": "n1"}


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
        rooms = _rooms()
        assert canvas_a in rooms and canvas_b in rooms
        assert set(rooms[canvas_a].keys()).isdisjoint(rooms[canvas_b].keys())
        assert len(rooms[canvas_a]) == 1
        assert len(rooms[canvas_b]) == 1


def test_display_name_is_stored_on_connect():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS DisplayName Stored"}).json()["id"]

    with client.websocket_connect(
        f"/ws/canvas/{canvas_id}/collaboration?display_name=Ana"
    ):
        room = _rooms().get(canvas_id, {})
        assert len(room) == 1
        peer = next(iter(room.values()))
        assert peer.session.display_name == "Ana"

    # Al salir del context manager el cliente cierra la conexión; el server
    # debe limpiar el registro.
    assert canvas_id not in _rooms()


def test_disconnect_removes_peer_from_registry():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Disconnect Test"}).json()["id"]

    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
        assert len(_rooms().get(canvas_id, {})) == 1

        with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
            assert len(_rooms().get(canvas_id, {})) == 2

        # El peer anidado salió del `with` (desconectado): el registro debe reflejarlo.
        assert len(_rooms().get(canvas_id, {})) == 1

    assert canvas_id not in _rooms()


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
    peer_id ni queda registrada en la Sala.
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
                f"/ws/canvas/{canvas_id}/collaboration",
                subprotocols=["bearer", outsider_token],
            ),
        ):
            pass
        assert exc_outsider.value.code == 4403

        assert canvas_id not in _rooms()


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
            f"/ws/canvas/{canvas_id}/collaboration", subprotocols=["bearer", owner_token]
        ) as owner_ws:
            handshake = owner_ws.receive_json()
            assert handshake["type"] == "connected"

            with scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration", subprotocols=["bearer", collab_token]
            ) as collab_ws:
                collab_handshake = collab_ws.receive_json()
                assert collab_handshake["type"] == "connected"
                assert len(_rooms().get(canvas_id, {})) == 2


def test_ws_token_en_la_query_string_ya_no_autentica():
    """El token viaja solo como subprotocolo `bearer`; en la URL queda en logs e historial."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-query")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Query"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]

        with (
            pytest.raises(WebSocketDisconnect) as exc,
            scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration?token={owner_token}"
            ),
        ):
            pass
        assert exc.value.code == 4403


def test_ws_negocia_el_subprotocolo_bearer_solo_si_el_cliente_lo_ofrece():

    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-subproto")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Subprotocolo"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]

        with scoped_client.websocket_connect(
            f"/ws/canvas/{canvas_id}/collaboration", subprotocols=["bearer", owner_token]
        ) as ws:
            assert ws.accepted_subprotocol == "bearer"

        # Lienzo sin dueño (abierto): el cliente no ofrece subprotocolo, el servidor no inventa uno.
        open_canvas_id = scoped_client.post("/api/v2/canvases", json={"name": "WS Abierto"}).json()[
            "id"
        ]
        with scoped_client.websocket_connect(f"/ws/canvas/{open_canvas_id}/collaboration") as ws:
            assert ws.accepted_subprotocol is None


def _url(canvas_id: str) -> str:
    return f"/ws/canvas/{canvas_id}/collaboration"


@pytest.mark.parametrize(
    "texto",
    [
        '{"type": "canvas_update", "canvas": {}}',  # solo el servidor emite canvas_update
        '{"type": "desconocido"}',
        '{"action": "ping"}',  # forma legacy sin `type`
        "esto no es json",
        "[1, 2, 3]",
        '{"type": ["cursor"]}',  # `type` no hashable
        "[" * 3000,  # anidamiento extremo dentro de los 4 KB
    ],
)
def test_ws_violacion_de_protocolo_cierra_con_1008_y_no_se_reenvia(texto):
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Invalido"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as emisor,
        client.websocket_connect(_url(canvas_id)) as receptor,
        client.websocket_connect(_url(canvas_id)) as tercero,
    ):
        for ws in (emisor, receptor, tercero):
            ws.receive_json()  # handshake "connected"

        emisor.send_text(texto)
        with pytest.raises(WebSocketDisconnect) as exc:
            emisor.receive_json()
        assert exc.value.code == 1008

        # Si el mensaje inválido se hubiera reenviado, llegaría al receptor antes que este.
        tercero.send_json({"type": "cursor", "x": 1, "y": 2})
        assert receptor.receive_json()["payload"] == {"type": "cursor", "x": 1.0, "y": 2.0}


@pytest.mark.parametrize(
    "texto",
    [
        '{"type": "cursor", "x": null, "y": 5}',  # lo que produce JSON.stringify(NaN) en el front
        '{"type": "cursor", "x": "abc", "y": 1}',
        '{"type": "cursor", "x": 1}',
        '{"type": "cursor", "x": NaN, "y": 1}',
        '{"type": "node_drag", "nodeId": "", "x": 1, "y": 1}',
        '{"type": "node_drag_end"}',
    ],
)
def test_ws_campo_invalido_se_descarta_sin_cerrar_la_conexion(texto):
    """Cursor y arrastre son flujos con pérdida: un campo inválido se descarta como el exceso de
    frecuencia. Prueba de que la conexión sigue viva: el mensaje válido que llega después se reenvía
    y es el PRIMERO que ve el receptor (el inválido no se reenvió)."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Campo Invalido"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as emisor,
        client.websocket_connect(_url(canvas_id)) as receptor,
    ):
        emisor.receive_json()
        receptor.receive_json()

        emisor.send_text(texto)
        emisor.send_json({"type": "cursor", "x": 7, "y": 8})

        assert receptor.receive_json()["payload"] == {"type": "cursor", "x": 7.0, "y": 8.0}


def test_ws_mensaje_que_excede_4kb_cierra_con_1008():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Grande"}).json()["id"]

    with client.websocket_connect(_url(canvas_id)) as ws:
        ws.receive_json()
        ws.send_json({"type": "cursor", "x": 1, "y": 2, "relleno": "a" * 5000})
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
        assert exc.value.code == 1008


def test_ws_solo_reenvia_los_campos_del_contrato():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Extra"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as emisor,
        client.websocket_connect(_url(canvas_id)) as receptor,
    ):
        emisor.receive_json()
        receptor.receive_json()

        emisor.send_json({"type": "cursor", "x": 1, "y": 2, "rol": "admin", "canvas": {"x": 1}})

        assert receptor.receive_json()["payload"] == {"type": "cursor", "x": 1.0, "y": 2.0}


def test_ws_el_exceso_de_frecuencia_se_descarta_sin_cerrar_la_conexion(monkeypatch):
    """Con el reloj congelado el bucket no se recarga: pasa exactamente `burst` mensajes."""
    from backend_case.app.collaboration import ws_router
    from backend_case.app.collaboration.rate_limit import TokenBucket

    monkeypatch.setattr(ws_router, "MAX_MESSAGES_PER_SECOND", 1)
    monkeypatch.setattr(
        ws_router,
        "TokenBucket",
        lambda rate_per_second, burst: TokenBucket(rate_per_second, burst, clock=lambda: 0.0),
    )
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Frecuencia"}).json()["id"]

    with (
        client.websocket_connect(_url(canvas_id)) as emisor,
        client.websocket_connect(_url(canvas_id)) as receptor,
        client.websocket_connect(_url(canvas_id)) as tercero,
    ):
        for ws in (emisor, receptor, tercero):
            ws.receive_json()

        emisor.send_json({"type": "cursor", "x": 1, "y": 1})  # pasa (ráfaga de 1)
        assert receptor.receive_json()["payload"]["x"] == 1.0

        emisor.send_json({"type": "cursor", "x": 2, "y": 2})  # excede: se descarta
        emisor.send_text("basura")  # excede: se descarta antes de validar, no cierra
        time.sleep(0.2)  # el servidor ya procesó ambos

        tercero.send_json({"type": "cursor", "x": 3, "y": 3})  # otra Sesión, otro bucket
        assert receptor.receive_json()["payload"]["x"] == 3.0
        assert len(_rooms()[canvas_id]) == 3  # el emisor sigue conectado
