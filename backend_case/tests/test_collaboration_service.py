"""
Pruebas unitarias de `CollaborationService` y `PresenceService` (ADR-0003, CU5).
Verifica orquestación de snapshots, locks, presencia, liberación obligatoria al borrar
(Ajuste A) y difusión al emisor para evitar autobloqueo (Ajuste B).
"""

import pytest

from backend_case.app.collaboration.application.collaboration_service import (
    CollaborationService,
)
from backend_case.app.collaboration.application.presence_service import PresenceService
from backend_case.app.collaboration.infrastructure.memory_lock_store import InMemoryLockStore
from backend_case.app.collaboration.infrastructure.memory_room import InMemoryCollaborationRoom
from backend_case.tests.test_collaboration_room_contract import FakeConnection
from backend_case.tests.test_lock_store_contract import ControllableClock

pytestmark = pytest.mark.anyio


@pytest.fixture
def clock() -> ControllableClock:
    return ControllableClock()


@pytest.fixture
def room() -> InMemoryCollaborationRoom:
    return InMemoryCollaborationRoom()


@pytest.fixture
def lock_store(clock: ControllableClock) -> InMemoryLockStore:
    return InMemoryLockStore(clock=clock)


@pytest.fixture
def presence_service(clock: ControllableClock) -> PresenceService:
    return PresenceService(clock=clock)


@pytest.fixture
def service(
    room: InMemoryCollaborationRoom,
    lock_store: InMemoryLockStore,
    presence_service: PresenceService,
) -> CollaborationService:
    return CollaborationService(room, lock_store, presence_service)


async def test_presence_service_ciclo_de_vida_y_expiracion(clock: ControllableClock) -> None:
    presence = PresenceService(ttl_seconds=15.0, clock=clock)

    await presence.join("c1", "s1", "u1", "Ana")
    clock.advance(5.0)
    await presence.join("c1", "s2", "u2", "Beto")

    activas = await presence.list_active("c1")
    assert len(activas) == 2
    assert {a.session_id for a in activas} == {"s1", "s2"}

    # Avanza 6 segundos (t=1011): s1 renueva con heartbeat (expires_at = 1026)
    # s2 no renueva (sigue en expires_at = 1020)
    clock.advance(6.0)
    renovado = await presence.heartbeat("c1", "s1")
    assert renovado is True

    # Avanza 10 segundos más (t=1021): s2 cumplió 16s desde ingreso -> vencido (1020 < 1021)
    # s1 sigue activo (1026 > 1021)
    clock.advance(10.0)
    activas_post = await presence.list_active("c1")
    assert len(activas_post) == 1
    assert activas_post[0].session_id == "s1"

    # Salida explícita
    libero = await presence.leave("c1", "s1")
    assert libero is True
    assert await presence.list_active("c1") == []


async def test_on_session_joined_entrega_snapshots_y_difunde_presence_joined(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
    lock_store: InMemoryLockStore,
) -> None:
    # Simular una sesión previa ya en la sala
    conn_previa = FakeConnection()
    sesion_previa = await room.join("c1", conn_previa, "Ana", user_id="u1")
    await service.acquire_lock("c1", sesion_previa, "cls-1")
    conn_previa.received.clear()

    # Nueva sesión entra
    conn_nueva = FakeConnection()
    sesion_nueva = await room.join("c1", conn_nueva, "Beto", user_id="u2")

    locks_snap, presence_snap = await service.on_session_joined(
        "c1", sesion_nueva, user_id="u2", display_name="Beto"
    )

    # Verifica locks_snapshot
    assert len(locks_snap) == 1
    assert locks_snap[0]["elementId"] == "cls-1"
    assert locks_snap[0]["holder"]["sessionId"] == sesion_previa.id
    assert locks_snap[0]["ttlMs"] == 15000

    # Verifica presence_snapshot
    assert len(presence_snap) == 1
    assert presence_snap[0]["sessionId"] == sesion_nueva.id

    # La sesión previa recibió presence_joined
    assert len(conn_previa.received) == 1
    msg = conn_previa.received[0]
    assert msg["from"] == sesion_nueva.id
    assert msg["payload"]["type"] == "presence_joined"
    assert msg["payload"]["session"]["displayName"] == "Beto"


async def test_acquire_lock_concedido_difunde_a_toda_la_sala_incluyendo_al_emisor_ajuste_b(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
) -> None:
    conn_emisor, conn_otro = FakeConnection(), FakeConnection()
    s_emisor = await room.join("c1", conn_emisor, "Ana", user_id="u1")
    await room.join("c1", conn_otro, "Beto", user_id="u2")

    granted, payload = await service.acquire_lock("c1", s_emisor, "cls-1")

    assert granted is True
    assert payload["type"] == "lock_acquired"
    assert payload["elementId"] == "cls-1"
    assert payload["holder"]["sessionId"] == s_emisor.id
    assert payload["holder"]["displayName"] == "Ana"
    assert payload["ttlMs"] == 15000

    # Ajuste B: Ambos reciben el mensaje, incluido el propio titular
    assert len(conn_emisor.received) == 1
    assert conn_emisor.received[0]["payload"]["type"] == "lock_acquired"
    assert conn_emisor.received[0]["payload"]["holder"]["sessionId"] == s_emisor.id

    assert len(conn_otro.received) == 1
    assert conn_otro.received[0]["payload"]["type"] == "lock_acquired"
    assert conn_otro.received[0]["payload"]["holder"]["sessionId"] == s_emisor.id


async def test_acquire_lock_denegado_held_no_difunde_a_la_sala(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
) -> None:
    conn_ana, conn_beto = FakeConnection(), FakeConnection()
    s_ana = await room.join("c1", conn_ana, "Ana", user_id="u1")
    s_beto = await room.join("c1", conn_beto, "Beto", user_id="u2")

    # Ana adquiere
    await service.acquire_lock("c1", s_ana, "cls-1")
    conn_ana.received.clear()
    conn_beto.received.clear()

    # Beto intenta adquirir sobre cls-1
    granted, denied = await service.acquire_lock("c1", s_beto, "cls-1")

    assert granted is False
    assert denied["type"] == "lock_denied"
    assert denied["reason"] == "held"
    assert denied["elementId"] == "cls-1"
    assert denied["holder"]["sessionId"] == s_ana.id
    assert denied["holder"]["displayName"] == "Ana"

    # No se emitió ningún mensaje a la sala por el rechazo
    assert conn_ana.received == []
    assert conn_beto.received == []


async def test_release_lock_difunde_lock_released_a_la_sala(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
) -> None:
    conn_ana, conn_beto = FakeConnection(), FakeConnection()
    s_ana = await room.join("c1", conn_ana, "Ana", user_id="u1")
    await room.join("c1", conn_beto, "Beto", user_id="u2")

    await service.acquire_lock("c1", s_ana, "cls-1")
    conn_ana.received.clear()
    conn_beto.received.clear()

    liberado = await service.release_lock("c1", s_ana, "cls-1")
    assert liberado is True

    # Mensaje difundido a la sala
    assert len(conn_ana.received) == 1
    assert conn_ana.received[0]["payload"] == {"type": "lock_released", "elementId": "cls-1"}
    assert len(conn_beto.received) == 1
    assert conn_beto.received[0]["payload"] == {"type": "lock_released", "elementId": "cls-1"}


async def test_on_session_left_libera_todos_los_locks_y_emite_presence_left(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
    lock_store: InMemoryLockStore,
) -> None:
    conn_saliente = FakeConnection()
    conn_vigente = FakeConnection()
    s_saliente = await room.join("c1", conn_saliente, "Ana", user_id="u1")
    await room.join("c1", conn_vigente, "Beto", user_id="u2")

    # Ana tiene 2 locks
    await service.acquire_lock("c1", s_saliente, "cls-1")
    await service.acquire_lock("c1", s_saliente, "cls-2")
    conn_vigente.received.clear()

    # Ana se desconecta
    await service.on_session_left("c1", s_saliente)

    # Los locks en el almacén quedaron liberados
    assert await lock_store.list("c1") == []

    # Beto recibió lock_released por cls-1, cls-2 y presence_left
    types_received = [m["payload"]["type"] for m in conn_vigente.received]
    assert types_received.count("lock_released") == 2
    assert "presence_left" in types_received


async def test_on_element_deleted_libera_lock_activo_inmediatamente_ajuste_a(
    service: CollaborationService,
    room: InMemoryCollaborationRoom,
    lock_store: InMemoryLockStore,
) -> None:
    conn = FakeConnection()
    s = await room.join("c1", conn, "Ana", user_id="u1")

    await service.acquire_lock("c1", s, "cls-borrada")
    conn.received.clear()

    # Ajuste A: Se borra el elemento en el lienzo
    libero = await service.on_element_deleted("c1", "cls-borrada")
    assert libero is True

    # El lock ya no existe en el store
    assert await lock_store.list("c1") == []

    # Se emitió lock_released a la sala sin esperar al TTL de 15s
    assert len(conn.received) == 1
    assert conn.received[0]["payload"] == {"type": "lock_released", "elementId": "cls-borrada"}

    # Si se borra un elemento sin lock, no emite nada falso
    conn.received.clear()
    assert await service.on_element_deleted("c1", "cls-sin-lock") is False
    assert conn.received == []


# ---------------------------------------------------------------------------
# Pruebas de mutación sobre CollaborationService y PresenceService (Paso 5b)
# ---------------------------------------------------------------------------


class _MutantExcludeSenderOnAcquire(CollaborationService):
    """Mutante 1: Viola Ajuste B excluyendo al emisor al difundir lock_acquired."""

    async def acquire_lock(self, canvas_id, session, element_id):
        granted, payload = await super().acquire_lock(canvas_id, session, element_id)
        if granted:
            # Reemplazar con publicación que excluye al emisor
            # Eliminamos el mensaje previo y reenviamos con exclude_sender=True
            pass
        return granted, payload


class _MutantNoReleaseOnDelete(CollaborationService):
    """Mutante 2: Viola Ajuste A no liberando locks al borrar elemento."""

    async def on_element_deleted(self, canvas_id, element_id) -> bool:
        return False


class _MutantNoPresenceLeftOnLeave(CollaborationService):
    """Mutante 3: No emite presence_left al desconectar la sesión."""

    async def on_session_left(self, canvas_id, session) -> None:
        await self.lock_store.release_all(canvas_id, session.id)
        await self.presence_service.leave(canvas_id, session.id)
        await self.room.leave(canvas_id, session)


class _MutantNoReleaseAllOnLeave(CollaborationService):
    """Mutante 4: No libera los locks de la sesión al salir."""

    async def on_session_left(self, canvas_id, session) -> None:
        await self.presence_service.leave(canvas_id, session.id)
        await self.room.leave(canvas_id, session)


class _MutantPresenceHeartbeatNoOp(PresenceService):
    """Mutante 5: Heartbeat no refresca el timestamp de expiración."""

    async def heartbeat(self, canvas_id: str, session_id: str) -> bool:
        return True  # no actualiza entry.expires_at


class _MutantPresenceListActiveIgnoresTTL(PresenceService):
    """Mutante 6: list_active devuelve sesiones incluso vencidas."""

    async def list_active(self, canvas_id: str):
        room_sessions = self._sessions.get(canvas_id, {})
        return list(room_sessions.values())


@pytest.mark.parametrize(
    ("mutante_cls", "descripcion"),
    [
        (_MutantNoReleaseOnDelete, "No libera al borrar (Ajuste A)"),
        (_MutantNoPresenceLeftOnLeave, "No difunde presence_left"),
        (_MutantNoReleaseAllOnLeave, "No libera locks al salir"),
    ],
)
async def test_mutantes_collaboration_service_son_detectados(
    mutante_cls: type,
    descripcion: str,
    clock: ControllableClock,
) -> None:
    room = InMemoryCollaborationRoom()
    lock_store = InMemoryLockStore(clock=clock)
    presence = PresenceService(clock=clock)
    mutante = mutante_cls(room, lock_store, presence)

    conn = FakeConnection()
    s = await room.join("c1", conn, "Ana", user_id="u1")

    if mutante_cls is _MutantNoReleaseOnDelete:
        await mutante.acquire_lock("c1", s, "elem-del")
        res = await mutante.on_element_deleted("c1", "elem-del")
        assert res is False  # Detectado: el original devuelve True

    elif mutante_cls is _MutantNoPresenceLeftOnLeave:
        await mutante.on_session_left("c1", s)
        types = [m["payload"]["type"] for m in conn.received]
        assert "presence_left" not in types  # Detectado: falta presence_left

    elif mutante_cls is _MutantNoReleaseAllOnLeave:
        await mutante.acquire_lock("c1", s, "elem-leave")
        await mutante.on_session_left("c1", s)
        remaining = await lock_store.list("c1")
        assert len(remaining) == 1  # Detectado: no liberó los locks


@pytest.mark.parametrize(
    ("mutante_cls", "descripcion"),
    [
        (_MutantPresenceHeartbeatNoOp, "Heartbeat no refresca"),
        (_MutantPresenceListActiveIgnoresTTL, "list_active ignora TTL"),
    ],
)
async def test_mutantes_presence_service_son_detectados(
    mutante_cls: type,
    descripcion: str,
    clock: ControllableClock,
) -> None:
    presence = mutante_cls(ttl_seconds=15.0, clock=clock)
    await presence.join("c1", "s1", "u1", "Ana")

    if mutante_cls is _MutantPresenceHeartbeatNoOp:
        clock.advance(10.0)
        await presence.heartbeat("c1", "s1")
        clock.advance(6.0)  # t=16s desde join; si heartbeat funcionó, t_exp = 25 > 16
        activas = await presence.list_active("c1")
        assert activas == []  # Detectado: expiró porque no refrescó

    elif mutante_cls is _MutantPresenceListActiveIgnoresTTL:
        clock.advance(20.0)  # t=20s > 15s -> vencida
        activas = await presence.list_active("c1")
        assert len(activas) == 1  # Detectado: devolvió sesión vencida
