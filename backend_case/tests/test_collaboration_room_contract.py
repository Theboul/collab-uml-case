"""
Contrato del puerto `CollaborationRoom`. Corre contra cada adaptador (hoy solo el de memoria; el de
Redis del Paso 6 se añade a `ADAPTERS`), así que describe lo que TODO adaptador debe cumplir.
"""

import json
from typing import Any

import pytest

from backend_case.app.collaboration.infrastructure.memory_room import InMemoryCollaborationRoom

pytestmark = pytest.mark.anyio


class FakeConnection:
    def __init__(self, fails: bool = False) -> None:
        self.received: list[dict] = []
        self.attempts = 0
        self._fails = fails

    async def send_text(self, data: str) -> None:
        self.attempts += 1
        if self._fails:
            raise RuntimeError("connection already closed")
        self.received.append(json.loads(data))


@pytest.fixture(params=["memoria", "redis"])
async def room(request: pytest.FixtureRequest) -> Any:
    if request.param == "memoria":
        yield InMemoryCollaborationRoom()
    elif request.param == "redis":
        import fakeredis
        import fakeredis.aioredis as fake_aioredis

        from backend_case.app.collaboration.infrastructure.redis_room import (
            RedisCollaborationRoom,
        )

        server = fakeredis.FakeServer()
        client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
        r = RedisCollaborationRoom(redis_client=client)
        try:
            yield r
        finally:
            await r.close()
    else:
        raise ValueError(f"Adaptador desconocido: {request.param}")


async def test_join_devuelve_una_sesion_distinta_por_conexion(room):
    a = await room.join("c1", FakeConnection())
    b = await room.join("c1", FakeConnection(), "Ana")
    assert a.id != b.id
    assert (a.display_name, b.display_name) == (None, "Ana")


async def test_publish_llega_a_las_demas_sesiones_y_no_al_emisor(room):
    emisor_conn, otra_conn = FakeConnection(), FakeConnection()
    emisor = await room.join("c1", emisor_conn, "Ana")
    await room.join("c1", otra_conn)

    await room.publish("c1", emisor.id, {"type": "cursor", "x": 1})

    assert otra_conn.received == [
        {"from": emisor.id, "fromDisplayName": "Ana", "payload": {"type": "cursor", "x": 1}}
    ]
    assert emisor_conn.received == []


async def test_publish_sin_sesion_de_origen_llega_a_todas(room):
    a, b = FakeConnection(), FakeConnection()
    await room.join("c1", a)
    await room.join("c1", b)

    await room.publish("c1", "", {"type": "canvas_update"})  # p. ej. un cambio hecho por HTTP

    esperado = [{"from": "", "fromDisplayName": None, "payload": {"type": "canvas_update"}}]
    assert a.received == esperado and b.received == esperado


async def test_las_salas_estan_aisladas_por_lienzo(room):
    en_c1, en_c2 = FakeConnection(), FakeConnection()
    await room.join("c1", en_c1)
    await room.join("c2", en_c2)

    await room.publish("c1", "", {"n": 1})

    assert len(en_c1.received) == 1 and en_c2.received == []


async def test_publicar_en_una_sala_sin_sesiones_no_hace_nada(room):
    await room.publish("nadie", "", {"n": 1})  # no lanza


async def test_una_conexion_caida_se_retira_sin_afectar_al_resto(room):
    viva, muerta = FakeConnection(), FakeConnection(fails=True)
    emisor = await room.join("c1", FakeConnection())
    await room.join("c1", viva)
    await room.join("c1", muerta)

    await room.publish("c1", emisor.id, {"n": 1})
    await room.publish("c1", emisor.id, {"n": 2})

    assert [m["payload"]["n"] for m in viva.received] == [1, 2]
    assert muerta.attempts == 1  # tras fallar se la retiró: no se vuelve a intentar


async def test_leave_retira_la_sesion_y_es_idempotente(room):
    salio = FakeConnection()
    emisor = await room.join("c1", FakeConnection())
    sesion = await room.join("c1", salio)

    await room.leave("c1", sesion)
    await room.leave("c1", sesion)  # segunda vez: no lanza
    await room.publish("c1", emisor.id, {"n": 1})

    assert salio.received == []


async def test_leave_de_la_ultima_sesion_o_de_un_lienzo_desconocido_no_lanza(room):
    sola = await room.join("c1", FakeConnection())
    await room.leave("c1", sola)
    await room.leave("c1", sola)
    await room.leave("desconocido", sola)


async def test_members_devuelve_las_sesiones_activas(room):
    a = await room.join("c1", FakeConnection(), "Ana", user_id="u1")
    b = await room.join("c1", FakeConnection(), "Beto", user_id="u2")

    miembros = await room.members("c1")
    assert len(miembros) == 2
    ids = {m.id for m in miembros}
    assert ids == {a.id, b.id}

    # Tras salir una, solo queda la otra
    await room.leave("c1", a)
    restantes = await room.members("c1")
    assert len(restantes) == 1
    assert restantes[0].id == b.id

    # Lienzo sin miembros devuelve lista vacía
    assert await room.members("vacio") == []


async def test_publish_con_exclude_sender_falso_llega_tambien_al_emisor(room):
    emisor_conn, otra_conn = FakeConnection(), FakeConnection()
    emisor = await room.join("c1", emisor_conn, "Ana")
    await room.join("c1", otra_conn, "Beto")

    payload = {"type": "lock_acquired", "elementId": "cls-1"}
    await room.publish("c1", emisor.id, payload, exclude_sender=False)

    esperado = [{"from": emisor.id, "fromDisplayName": "Ana", "payload": payload}]
    assert emisor_conn.received == esperado
    assert otra_conn.received == esperado


async def test_multi_worker_broadcast_llega_a_sesion_en_otro_worker() -> None:
    """Verifica que un mensaje publicado en Worker 1 llegue a una sesión conectada a Worker 2."""
    import asyncio

    import fakeredis
    import fakeredis.aioredis as fake_aioredis

    from backend_case.app.collaboration.infrastructure.redis_room import (
        RedisCollaborationRoom,
    )

    server = fakeredis.FakeServer()
    w1_client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    w2_client = fake_aioredis.FakeRedis(server=server, decode_responses=True)

    room_w1 = RedisCollaborationRoom(redis_client=w1_client)
    room_w2 = RedisCollaborationRoom(redis_client=w2_client)

    conn_ana = FakeConnection()
    conn_beto = FakeConnection()

    ana = await room_w1.join("c1", conn_ana, "Ana")
    await room_w2.join("c1", conn_beto, "Beto")

    # Permitir que el worker 2 termine su subscripción en el event loop
    await asyncio.sleep(0.02)

    payload = {"type": "cursor", "x": 100, "y": 200}
    await room_w1.publish("c1", ana.id, payload, exclude_sender=True)

    # Permitir entrega asíncrona de pubsub
    await asyncio.sleep(0.03)

    assert len(conn_beto.received) == 1
    assert conn_beto.received[0] == {
        "from": ana.id,
        "fromDisplayName": "Ana",
        "payload": payload,
    }
    assert conn_ana.received == []

    await room_w1.close()
    await room_w2.close()


async def test_anti_eco_no_duplica_mensajes_en_clientes_locales() -> None:
    """Verifica que los clientes locales no reciban el mensaje por duplicado a través del PubSub."""
    import asyncio

    import fakeredis
    import fakeredis.aioredis as fake_aioredis

    from backend_case.app.collaboration.infrastructure.redis_room import (
        RedisCollaborationRoom,
    )

    server = fakeredis.FakeServer()
    client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    room = RedisCollaborationRoom(redis_client=client)

    conn_ana = FakeConnection()
    conn_carlos = FakeConnection()

    ana = await room.join("c1", conn_ana, "Ana")
    await room.join("c1", conn_carlos, "Carlos")

    await asyncio.sleep(0.02)

    payload = {"type": "lock_acquired", "elementId": "cls-1"}
    await room.publish("c1", ana.id, payload, exclude_sender=False)

    # Esperar propagación de pubsub
    await asyncio.sleep(0.03)

    # Ambos deben haber recibido el mensaje exactamente una vez (entrega local inmediata, sin eco)
    assert len(conn_ana.received) == 1
    assert len(conn_carlos.received) == 1
    assert conn_ana.received[0]["payload"] == payload
    assert conn_carlos.received[0]["payload"] == payload

    await room.close()
