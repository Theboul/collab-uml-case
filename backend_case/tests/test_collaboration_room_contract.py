"""
Contrato del puerto `CollaborationRoom`. Corre contra cada adaptador (hoy solo el de memoria; el de
Redis del Paso 6 se añade a `ADAPTERS`), así que describe lo que TODO adaptador debe cumplir.
"""

import json

import pytest

from backend_case.app.collaboration.infrastructure.memory_room import InMemoryCollaborationRoom

pytestmark = pytest.mark.anyio

ADAPTERS = {"memoria": InMemoryCollaborationRoom}


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


@pytest.fixture(params=list(ADAPTERS))
def room(request):
    return ADAPTERS[request.param]()


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
