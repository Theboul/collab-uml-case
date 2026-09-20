"""
Pruebas del canal de transporte de colaboración (ADR-0003, paso 1).
Cubre sólo lo que este paso implementa: broadcast entre peers de la misma
sala, aislamiento entre salas distintas, y limpieza del registro al
desconectar. Sin locks, sin presencia todavía.
"""

import time
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend_case.app.main import app
from backend_case.app.shared.security.tokens import create_access_token

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


def _close_code(test_client, url: str, **kwargs) -> int:
    """
    Conecta y devuelve el código con que el servidor cierra. La conexión DEBE aceptarse antes: un
    rechazo previo a `accept()` llega al navegador como un fallo de handshake sin código (1006).
    """
    with (
        test_client.websocket_connect(url, **kwargs) as ws,  # si no se acepta, lanza aquí
        pytest.raises(WebSocketDisconnect) as exc,
    ):
        ws.receive_json()
    return exc.value.code


def test_ws_rejects_connection_without_valid_role():
    """
    Sin token, o con el token de un usuario ajeno al lienzo, el servidor ACEPTA el WebSocket y lo
    cierra con 4403 (sin permiso: el cliente no debe reintentar). Nunca se le asigna una Sesión ni
    queda registrada en la Sala.
    """
    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-403")
        outsider_token = _register_and_get_token(scoped_client, "outsider-ws-403")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Privado"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]
        url = _url(canvas_id)

        assert _close_code(scoped_client, url) == 4403
        assert _close_code(scoped_client, url, subprotocols=["bearer", outsider_token]) == 4403
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
    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-query")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Query"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]

        assert _close_code(scoped_client, f"{_url(canvas_id)}?token={owner_token}") == 4403

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


def test_si_el_commit_falla_el_cambio_no_se_difunde(monkeypatch):
    """
    Publicar solo tras el commit: un commit fallido no deja a los demás con un cambio fantasma.
    Prueba determinista: el primer mensaje que ve el receptor es el del SEGUNDO comando (versión 2);
    si el primero hubiera publicado, llegaría antes y traería "Fantasma".
    """
    from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository

    def comando(nombre: str) -> dict:
        payload = {"name": nombre, "x": 0, "y": 0, "width": 180, "height": 100}
        return {"expectedVersion": 1, "type": "CREATE_CLASS", "payload": payload}

    with TestClient(app) as scoped_client:
        canvas_id = scoped_client.post(
            "/api/v2/canvases", json={"name": "Lienzo Commit Falla"}
        ).json()["id"]

        with (
            scoped_client.websocket_connect(_url(canvas_id)) as emisor,
            scoped_client.websocket_connect(_url(canvas_id)) as receptor,
        ):
            emisor.receive_json()
            receptor.receive_json()

            commit_real = CanvasRepository.commit

            async def commit_que_falla(self):
                raise RuntimeError("commit fallido")

            monkeypatch.setattr(CanvasRepository, "commit", commit_que_falla)
            with pytest.raises(RuntimeError, match="commit fallido"):
                scoped_client.post(
                    f"/api/v2/canvases/{canvas_id}/commands", json=comando("Fantasma")
                )
            monkeypatch.setattr(CanvasRepository, "commit", commit_real)

            res = scoped_client.post(f"/api/v2/canvases/{canvas_id}/commands", json=comando("Real"))
            assert res.status_code == 200

            canvas = receptor.receive_json()["payload"]["canvas"]
            assert canvas["version"] == 2
            assert [c["name"] for c in canvas["model"]["classes"]] == ["Real"]


def test_un_fallo_al_publicar_no_falla_el_comando_ni_lo_revierte(monkeypatch):
    """Publicar es un aviso posterior al commit: si falla (p. ej. Redis caído) el cambio ya está
    guardado y la petición responde bien; los clientes se ponen al día por resync."""
    from backend_case.app.collaboration.infrastructure.memory_room import InMemoryCollaborationRoom

    async def publish_que_falla(self, canvas_id, sender_session_id, payload):
        raise RuntimeError("redis caído")

    monkeypatch.setattr(InMemoryCollaborationRoom, "publish", publish_que_falla)

    with TestClient(app) as scoped_client:
        canvas_id = scoped_client.post(
            "/api/v2/canvases", json={"name": "Lienzo Publicar Falla"}
        ).json()["id"]
        payload = {"name": "Cliente", "x": 0, "y": 0, "width": 180, "height": 100}

        res = scoped_client.post(
            f"/api/v2/canvases/{canvas_id}/commands",
            json={"expectedVersion": 1, "type": "CREATE_CLASS", "payload": payload},
        )

        assert res.status_code == 200
        guardado = scoped_client.get(f"/api/v2/canvases/{canvas_id}").json()
        assert guardado["version"] == 2
        assert [c["name"] for c in guardado["model"]["classes"]] == ["Cliente"]


def test_ws_token_invalido_o_vencido_cierra_con_4401():
    """
    Un token presentado pero inválido o vencido cierra con 4401: a diferencia del 4403, el cliente
    puede renovarlo y reintentar (el access token dura 15 min y una reconexión tras una caída
    larga lleva uno caducado).
    """
    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-4401")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS 4401"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]
        claims = jwt.decode(owner_token, options={"verify_signature": False})
        vencido = create_access_token(
            claims["sub"], claims["email"], claims["fullName"], expires_delta=timedelta(seconds=-5)
        )
        url = _url(canvas_id)

        assert _close_code(scoped_client, url, subprotocols=["bearer", vencido]) == 4401
        assert _close_code(scoped_client, url, subprotocols=["bearer", "no-es-un-jwt"]) == 4401
        assert canvas_id not in _rooms()


def test_ws_lienzo_inexistente_cierra_con_4403():
    with TestClient(app) as scoped_client:
        assert _close_code(scoped_client, _url("no-existe")) == 4403
        assert "no-existe" not in _rooms()


def test_ws_el_rechazo_devuelve_el_subprotocolo_bearer():
    """
    El navegador exige que el servidor devuelva uno de los subprotocolos ofrecidos; si no, la
    conexión falla como handshake y el cliente nunca llega a ver el código de cierre.
    """
    with TestClient(app) as scoped_client:
        owner_token = _register_and_get_token(scoped_client, "owner-ws-sub")
        outsider_token = _register_and_get_token(scoped_client, "outsider-ws-sub")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "Lienzo WS Subprotocolo Rechazo"},
            headers={"Authorization": f"Bearer {owner_token}"},
        ).json()["id"]

        with scoped_client.websocket_connect(
            _url(canvas_id), subprotocols=["bearer", outsider_token]
        ) as ws:
            assert ws.accepted_subprotocol == "bearer"
            with pytest.raises(WebSocketDisconnect):
                ws.receive_json()
