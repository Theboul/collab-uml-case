"""
Tests de contrato para implementaciones de `PresenceService` (ADR-0003 y su Addendum).

Valida tanto `InMemoryPresenceService` como `RedisPresenceService` con fakeredis
y reloj determinístico sin sleep real.
"""

from collections.abc import Callable
from unittest.mock import patch

import fakeredis
import fakeredis.aioredis as fake_aioredis
import pytest

from backend_case.app.collaboration.application.presence_service import (
    PRESENCE_TTL_SECONDS,
    InMemoryPresenceService,
    PresenceService,
)
from backend_case.app.collaboration.infrastructure.redis_presence_service import (
    RedisPresenceService,
)
from backend_case.tests.test_lock_store_contract import ControllableClock

pytestmark = pytest.mark.anyio

PresenceFactory = Callable[[Callable[[], float]], PresenceService]


@pytest.fixture
def clock() -> ControllableClock:
    return ControllableClock()


@pytest.fixture(params=["memory", "redis"])
def service_factory(request: pytest.FixtureRequest) -> PresenceFactory:
    if request.param == "memory":
        return lambda c: InMemoryPresenceService(clock=c)
    if request.param == "redis":

        def _create_redis_service(c: Callable[[], float]) -> PresenceService:
            patcher = patch("time.time", side_effect=c)
            patcher.start()
            request.addfinalizer(patcher.stop)

            server = fakeredis.FakeServer()
            client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
            return RedisPresenceService(redis_client=client, clock=c)

        return _create_redis_service
    raise ValueError(f"Servicio desconocido: {request.param}")


@pytest.fixture
def presence(service_factory: PresenceFactory, clock: ControllableClock) -> PresenceService:
    return service_factory(clock)


async def test_join_registra_sesion_con_datos_y_ttl(
    presence: PresenceService, clock: ControllableClock
) -> None:
    p = await presence.join("c1", "s1", "u1", "Ana García")
    assert p.session_id == "s1"
    assert p.user_id == "u1"
    assert p.display_name == "Ana García"
    assert p.expires_at == clock() + PRESENCE_TTL_SECONDS

    activas = await presence.list_active("c1")
    assert len(activas) == 1
    assert activas[0].session_id == "s1"
    assert activas[0].display_name == "Ana García"


async def test_heartbeat_renueva_sesion_vigente(
    presence: PresenceService, clock: ControllableClock
) -> None:
    await presence.join("c1", "s1", "u1", "Ana")

    # Avanzar 5 segundos
    clock.advance(5.0)
    renovado = await presence.heartbeat("c1", "s1")
    assert renovado is True

    # La sesión activa debe reflejar la nueva expiración extendida
    activas = await presence.list_active("c1")
    assert len(activas) == 1
    assert activas[0].expires_at == clock() + PRESENCE_TTL_SECONDS


async def test_heartbeat_sesion_inexistente_o_vencida_devuelve_false(
    presence: PresenceService, clock: ControllableClock
) -> None:
    # Sesión que nunca se unió
    assert await presence.heartbeat("c1", "fantasma") is False

    # Sesión que se unió y venció
    await presence.join("c1", "s1", "u1", "Ana")
    clock.advance(15.0)

    # Intento de heartbeat sobre sesión ya vencida: debe retornar False y no revivirla
    assert await presence.heartbeat("c1", "s1") is False
    assert await presence.list_active("c1") == []


async def test_leave_retira_sesion_y_es_idempotente(presence: PresenceService) -> None:
    await presence.join("c1", "s1", "u1", "Ana")
    assert len(await presence.list_active("c1")) == 1

    # Primer leave: exitoso
    assert await presence.leave("c1", "s1") is True
    assert await presence.list_active("c1") == []

    # Segundo leave sobre la misma sesión: idempotente devuelve False
    assert await presence.leave("c1", "s1") is False


async def test_vencimiento_automatico_a_los_15_segundos(
    presence: PresenceService, clock: ControllableClock
) -> None:
    await presence.join("c1", "s1", "u1", "Ana")

    # A los 14.9 s sigue activa
    clock.advance(14.9)
    activas = await presence.list_active("c1")
    assert len(activas) == 1
    assert activas[0].session_id == "s1"

    # A los 15.0 s expira automáticamente
    clock.advance(0.1)
    activas_post = await presence.list_active("c1")
    assert len(activas_post) == 0


async def test_aislamiento_entre_lienzos(presence: PresenceService) -> None:
    await presence.join("c1", "s1", "u1", "Ana")
    await presence.join("c2", "s2", "u2", "Beto")

    activas_c1 = await presence.list_active("c1")
    activas_c2 = await presence.list_active("c2")

    assert len(activas_c1) == 1 and activas_c1[0].session_id == "s1"
    assert len(activas_c2) == 1 and activas_c2[0].session_id == "s2"
