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
from backend_case.tests.canvas_delta_contract import validate_canvas_delta_message

client = TestClient(app)


def _rooms() -> dict:
    """Estado interno del adaptador en memoria; solo para inspeccionar en tests."""
    return app.state.collaboration_room.rooms


def _drain_connect(ws) -> dict:
    """Consume connected, locks_snapshot, presence_snapshot y devuelve el handshake connected."""
    conn = ws.receive_json()
    assert conn["type"] == "connected"
    locks = ws.receive_json()
    assert locks["type"] == "locks_snapshot"
    presence = ws.receive_json()
    assert presence["type"] == "presence_snapshot"
    return conn


def test_broadcast_reaches_other_peers_in_same_room_not_the_sender():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Broadcast Test"}).json()["id"]

    with (
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws1,
        client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
    ):
        _drain_connect(ws1)
        _drain_connect(ws2)
        # ws1 recibe presence_joined de ws2
        joined = ws1.receive_json()
        assert joined["payload"]["type"] == "presence_joined"

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
    ADR-0003 paso 2 y Decisión 1 del Paso 5: el display_name proviene del usuario autenticado
    en el servidor (no de query params). Verifica que viaja por el envelope real.
    """
    with TestClient(app) as scoped_client:
        token_ana = _register_and_get_token(scoped_client, "ana_bcast", full_name="Ana")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "WS DisplayName Test"},
        ).json()["id"]

        with (
            scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration",
                subprotocols=["bearer", token_ana],
            ) as ws1,
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
        ):
            _drain_connect(ws1)
            _drain_connect(ws2)
            ws1.receive_json()  # presence_joined de ws2

            ws1.send_json({"type": "cursor", "x": 10, "y": 20})
            received = ws2.receive_json()
            assert received["fromDisplayName"] == "Ana"

            # El peer sin autenticar (display_name None) manda None, no revienta
            ws2.send_json({"type": "cursor", "x": 1, "y": 2})
            received_back = ws1.receive_json()
            assert received_back["fromDisplayName"] is None


def test_peers_in_different_canvas_are_registered_in_separate_rooms():
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
    """Decisión 1: display_name proviene de la autenticación del usuario."""
    with TestClient(app) as scoped_client:
        token_ana = _register_and_get_token(scoped_client, "ana_reg", full_name="Ana")
        canvas_id = scoped_client.post(
            "/api/v2/canvases",
            json={"name": "WS DisplayName Stored"},
            headers={"Authorization": f"Bearer {token_ana}"},
        ).json()["id"]

        with scoped_client.websocket_connect(
            f"/ws/canvas/{canvas_id}/collaboration",
            subprotocols=["bearer", token_ana],
        ):
            room = _rooms().get(canvas_id, {})
            assert len(room) == 1
            peer = next(iter(room.values()))
            assert peer.session.display_name == "Ana"

        assert canvas_id not in _rooms()


def test_query_display_name_is_ignored_for_security():
    """Decisión 1: ?display_name= en la URL se ignora para evitar suplantación de identidad."""
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Query Ignored"}).json()["id"]
    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration?display_name=Impostor"):
        room = _rooms().get(canvas_id, {})
        peer = next(iter(room.values()))
        assert peer.session.display_name is None


def test_disconnect_removes_peer_from_registry():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Disconnect Test"}).json()["id"]

    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
        assert len(_rooms().get(canvas_id, {})) == 1

        with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration"):
            assert len(_rooms().get(canvas_id, {})) == 2

        assert len(_rooms().get(canvas_id, {})) == 1

    assert canvas_id not in _rooms()


def test_connect_sends_peer_id_handshake():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Handshake Test"}).json()["id"]

    with client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws:
        handshake = ws.receive_json()
        assert handshake["type"] == "connected"
        assert isinstance(handshake["peerId"], str) and handshake["peerId"]
        # Además llegan los snapshots iniciales
        assert ws.receive_json()["type"] == "locks_snapshot"
        assert ws.receive_json()["type"] == "presence_snapshot"


def test_http_command_broadcast_excludes_sender_via_peer_id():
    """
    Reproduce el escenario real: un comando ejecutado por HTTP con el peerId
    de la conexión WS activa del emisor no debe hacerle eco a ese mismo peer,
    pero sí debe llegar a los demás en la sala.
    """
    from fastapi.testclient import TestClient as _TestClient

    from backend_case.app.main import app as _app

    with _TestClient(_app) as scoped_client:
        canvas_id = scoped_client.post(
            "/api/v2/canvases", json={"name": "Lienzo Colab Peer"}
        ).json()["id"]

        with (
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws1,
            scoped_client.websocket_connect(f"/ws/canvas/{canvas_id}/collaboration") as ws2,
        ):
            ws1_conn = _drain_connect(ws1)
            ws1_peer_id = ws1_conn["peerId"]
            _drain_connect(ws2)
            ws1.receive_json()  # presence_joined de ws2

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
            assert received["from"] == ws1_peer_id
            mensaje = received["payload"]
            assert mensaje["type"] == "canvas_delta"
            assert (mensaje["fromVersion"], mensaje["toVersion"]) == (1, 2)
            (clase,) = mensaje["delta"]["model"]["classes"]["upsert"]
            assert clase["name"] == "Cliente"
            validate_canvas_delta_message(mensaje)  # lo que viaja de verdad cumple el contrato


def _register_and_get_token(
    client_: TestClient, email_prefix: str, full_name: str = "Test User"
) -> str:
    """El sufijo uuid evita choques de email si el archivo SQLite persiste entre corridas."""
    import uuid as _uuid

    email = f"{email_prefix}-{_uuid.uuid4().hex[:8]}@schemacraft.dev"
    res = client_.post(
        "/api/v2/auth/register",
        json={"email": email, "password": "Password123!", "fullName": full_name},
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
            handshake = _drain_connect(owner_ws)
            assert handshake["type"] == "connected"

            with scoped_client.websocket_connect(
                f"/ws/canvas/{canvas_id}/collaboration", subprotocols=["bearer", collab_token]
            ) as collab_ws:
                collab_handshake = _drain_connect(collab_ws)
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
        '{"type": "canvas_delta", "delta": {}}',  # solo el servidor emite canvas_delta
        '{"type": "canvas_update", "canvas": {}}',  # el mensaje que ya no existe
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
        _drain_connect(emisor)
        _drain_connect(receptor)
        _drain_connect(tercero)

        # emisor recibe presence_joined de receptor y tercero
        emisor.receive_json()
        emisor.receive_json()
        # receptor recibe presence_joined de tercero
        receptor.receive_json()

        emisor.send_text(texto)
        with pytest.raises(WebSocketDisconnect) as exc:
            emisor.receive_json()
        assert exc.value.code == 1008

        # receptor recibe presence_left de emisor
        left = receptor.receive_json()
        assert left["payload"]["type"] == "presence_left"

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
        _drain_connect(emisor)
        _drain_connect(receptor)
        emisor.receive_json()  # presence_joined de receptor

        emisor.send_text(texto)
        emisor.send_json({"type": "cursor", "x": 7, "y": 8})

        assert receptor.receive_json()["payload"] == {"type": "cursor", "x": 7.0, "y": 8.0}


def test_ws_mensaje_que_excede_4kb_cierra_con_1008():
    canvas_id = client.post("/api/v2/canvases", json={"name": "WS Grande"}).json()["id"]

    with client.websocket_connect(_url(canvas_id)) as ws:
        _drain_connect(ws)
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
        _drain_connect(emisor)
        _drain_connect(receptor)
        emisor.receive_json()  # presence_joined de receptor

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
        _drain_connect(emisor)
        _drain_connect(receptor)
        _drain_connect(tercero)
        emisor.receive_json()  # presence_joined de receptor
        emisor.receive_json()  # presence_joined de tercero
        receptor.receive_json()  # presence_joined de tercero

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
            _drain_connect(emisor)
            _drain_connect(receptor)
            emisor.receive_json()  # presence_joined de receptor

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

            mensaje = receptor.receive_json()["payload"]
            assert mensaje["type"] == "canvas_delta"
            assert (mensaje["fromVersion"], mensaje["toVersion"]) == (1, 2)
            nombres = [c["name"] for c in mensaje["delta"]["model"]["classes"]["upsert"]]
            assert nombres == ["Real"]  # sin "Fantasma"


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


def test_agregar_clase_y_asociacion_por_http_llegan_a_los_demas_como_delta():
    """POST /classes y POST /associations antes no difundían nada: ahora publican."""
    with TestClient(app) as scoped_client:
        creado = scoped_client.post("/api/v2/canvases", json={"name": "Lienzo Dedicados"})
        canvas_id = creado.json()["id"]

        with scoped_client.websocket_connect(_url(canvas_id)) as observador:
            _drain_connect(observador)

            base = f"/api/v2/canvases/{canvas_id}"
            a = scoped_client.post(f"{base}/classes", json={"name": "A"})
            assert a.status_code == 201
            b = scoped_client.post(f"{base}/classes", json={"name": "B"})
            ids = [c["id"] for c in b.json()["model"]["classes"]]
            asociacion = scoped_client.post(
                f"{base}/associations", json={"sourceClassId": ids[0], "targetClassId": ids[1]}
            )
            assert asociacion.status_code == 201

            mensajes = [observador.receive_json()["payload"] for _ in range(3)]

    assert [(m["fromVersion"], m["toVersion"]) for m in mensajes] == [(1, 2), (2, 3), (3, 4)]
    assert all(m["type"] == "canvas_delta" for m in mensajes)
    assert [c["name"] for c in mensajes[0]["delta"]["model"]["classes"]["upsert"]] == ["A"]
    assert [c["name"] for c in mensajes[1]["delta"]["model"]["classes"]["upsert"]] == ["B"]
    assert set(mensajes[2]["delta"]["model"]) == {"associations"}
