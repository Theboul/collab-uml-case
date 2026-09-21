"""
Pruebas de la función de arranque e inyección fail-fast (_build_collaboration_infra).
Verifica:
1. Sin REDIS_URL -> inyección de adaptadores en memoria.
2. Con REDIS_URL y ping exitoso -> inyección de adaptadores Redis.
3. Con REDIS_URL y fallo de ping o timeout -> RuntimeError explícito (fail-fast).
"""

from unittest.mock import AsyncMock, patch

import fakeredis
import fakeredis.aioredis as fake_aioredis
import pytest

from backend_case.app.collaboration.application.presence_service import (
    InMemoryPresenceService,
)
from backend_case.app.collaboration.infrastructure.memory_lock_store import (
    InMemoryLockStore,
)
from backend_case.app.collaboration.infrastructure.memory_room import (
    InMemoryCollaborationRoom,
)
from backend_case.app.collaboration.infrastructure.redis_lock_store import (
    RedisLockStore,
)
from backend_case.app.collaboration.infrastructure.redis_presence_service import (
    RedisPresenceService,
)
from backend_case.app.collaboration.infrastructure.redis_room import (
    RedisCollaborationRoom,
)
from backend_case.app.main import _build_collaboration_infra

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("redis_url", ["", "   ", None])
async def test_build_collaboration_infra_sin_redis_url_usa_memoria(
    redis_url: str | None,
) -> None:
    url_to_test = "" if redis_url is None else redis_url.strip()
    lock_store, presence_service, room, redis_client = await _build_collaboration_infra(url_to_test)

    assert isinstance(lock_store, InMemoryLockStore)
    assert isinstance(presence_service, InMemoryPresenceService)
    assert isinstance(room, InMemoryCollaborationRoom)
    assert redis_client is None


async def test_build_collaboration_infra_con_redis_valido_inyecta_adaptadores_redis() -> None:
    server = fakeredis.FakeServer()
    fake_client = fake_aioredis.FakeRedis(server=server, decode_responses=True)

    with patch("redis.asyncio.from_url", return_value=fake_client):
        lock_store, presence_service, room, client = await _build_collaboration_infra(
            "redis://127.0.0.1:6379/0"
        )

    try:
        assert isinstance(lock_store, RedisLockStore)
        assert isinstance(presence_service, RedisPresenceService)
        assert isinstance(room, RedisCollaborationRoom)
        assert client is fake_client
    finally:
        await room.close()
        await client.aclose()


async def test_build_collaboration_infra_con_error_conexion_lanza_runtime_error() -> None:
    mock_client = AsyncMock()
    mock_client.ping.side_effect = ConnectionError("Connection refused")
    mock_client.aclose = AsyncMock()

    with (
        patch("redis.asyncio.from_url", return_value=mock_client),
        pytest.raises(RuntimeError, match="REDIS_URL está configurada"),
    ):
        await _build_collaboration_infra("redis://127.0.0.1:6379/0")

    mock_client.aclose.assert_awaited_once()


async def test_build_collaboration_infra_con_timeout_ping_lanza_runtime_error() -> None:
    mock_client = AsyncMock()
    mock_client.ping.side_effect = TimeoutError("timed out")
    mock_client.aclose = AsyncMock()

    with (
        patch("redis.asyncio.from_url", return_value=mock_client),
        pytest.raises(RuntimeError, match="REDIS_URL está configurada"),
    ):
        await _build_collaboration_infra("redis://127.0.0.1:6379/0")

    mock_client.aclose.assert_awaited_once()
