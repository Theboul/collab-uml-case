"""
Tests de contrato para implementaciones de `LockStore` (ADR-0003 y su Addendum).

El contrato es parametrizable para validar tanto `InMemoryLockStore` (Paso 5a)
como el futuro adaptador Redis (Paso 6).
"""

from collections.abc import Callable
from typing import Any

import pytest

from backend_case.app.collaboration.application.ports.lock_store import (
    LOCK_TTL_SECONDS,
    MAX_LOCKS_PER_SESSION,
    LockHolder,
    LockStore,
)
from backend_case.app.collaboration.infrastructure.memory_lock_store import InMemoryLockStore


class ControllableClock:
    """Reloj determinístico para probar vencimientos y renovaciones sin `time.sleep`."""

    def __init__(self, initial: float = 1000.0) -> None:
        self.current = initial

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


StoreFactory = Callable[[Callable[[], float]], LockStore]


@pytest.fixture
def clock() -> ControllableClock:
    return ControllableClock()


@pytest.fixture(params=["memory", "redis"])
def store_factory(request: pytest.FixtureRequest) -> StoreFactory:
    if request.param == "memory":
        return lambda c: InMemoryLockStore(clock=c)
    if request.param == "redis":
        from unittest.mock import patch

        import fakeredis
        import fakeredis.aioredis as fake_aioredis

        from backend_case.app.collaboration.infrastructure.redis_lock_store import RedisLockStore

        def _create_redis_store(c: Callable[[], float]) -> LockStore:
            patcher = patch("time.time", side_effect=c)
            patcher.start()
            request.addfinalizer(patcher.stop)

            server = fakeredis.FakeServer()
            client = fake_aioredis.FakeRedis(server=server, decode_responses=True)
            return RedisLockStore(redis_client=client, clock=c)

        return _create_redis_store
    raise ValueError(f"Almacén desconocido: {request.param}")


@pytest.fixture
def store(store_factory: StoreFactory, clock: ControllableClock) -> LockStore:
    return store_factory(clock)


@pytest.mark.anyio
async def test_adquirir_lock_exitoso(store: LockStore, clock: ControllableClock) -> None:
    holder = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    res = await store.acquire("canvas-1", "elem-1", holder)

    assert res.granted is True
    assert res.reason is None
    assert res.lock is not None
    assert res.lock.element_id == "elem-1"
    assert res.lock.holder == holder
    assert res.lock.expires_at == clock() + LOCK_TTL_SECONDS


@pytest.mark.anyio
async def test_renovar_lock_idempotente_mismo_titular_extiende_expiracion(
    store: LockStore, clock: ControllableClock
) -> None:
    holder = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    res1 = await store.acquire("canvas-1", "elem-1", holder)
    assert res1.granted is True

    # Avanza 5 segundos (heartbeat normal del cliente)
    clock.advance(5.0)

    # Renueva el lock con la misma sesión
    updated_holder = LockHolder(session_id="s1", user_id="u1", display_name="Ana (Editada)")
    res2 = await store.acquire("canvas-1", "elem-1", updated_holder)

    assert res2.granted is True
    assert res2.reason is None
    assert res2.lock is not None
    assert res2.lock.holder == updated_holder
    # La nueva expiración se extendió 15 s a partir de t=1005 -> 1020
    assert res2.lock.expires_at == clock() + LOCK_TTL_SECONDS


@pytest.mark.anyio
async def test_rechazo_held_cuando_otra_sesion_lo_tiene_vigente(
    store: LockStore, clock: ControllableClock
) -> None:
    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    await store.acquire("canvas-1", "elem-1", ana)

    beto = LockHolder(session_id="s2", user_id="u2", display_name="Beto")
    res_beto = await store.acquire("canvas-1", "elem-1", beto)

    assert res_beto.granted is False
    assert res_beto.reason == "held"
    assert res_beto.lock is not None
    assert res_beto.lock.holder.session_id == "s1"
    assert res_beto.lock.holder.display_name == "Ana"


@pytest.mark.anyio
async def test_liberar_exitoso_solo_para_el_titular_real(
    store: LockStore, clock: ControllableClock
) -> None:
    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    await store.acquire("canvas-1", "elem-1", ana)

    # Beto intenta liberar el lock de Ana: debe fallar
    libero_beto = await store.release("canvas-1", "elem-1", session_id="s2")
    assert libero_beto is False

    # El lock sigue perteneciendo a Ana
    locks = await store.list("canvas-1")
    assert len(locks) == 1
    assert locks[0].element_id == "elem-1"

    # Ana lo libera: éxito
    libero_ana = await store.release("canvas-1", "elem-1", session_id="s1")
    assert libero_ana is True

    # El lock ya no existe
    locks_despues = await store.list("canvas-1")
    assert len(locks_despues) == 0


@pytest.mark.anyio
async def test_liberar_elemento_inexistente_devuelve_false(store: LockStore) -> None:
    libero = await store.release("canvas-1", "no-existe", session_id="s1")
    assert libero is False


@pytest.mark.anyio
async def test_force_release_libera_lock_sin_importar_titular(
    store: LockStore, clock: ControllableClock
) -> None:
    """force_release libera el lock independientemente de quién sea el titular."""
    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    await store.acquire("canvas-1", "elem-1", ana)

    # force_release no requiere session_id: lo libera directamente
    libero = await store.force_release("canvas-1", "elem-1")
    assert libero is True

    # El elemento ya no aparece en el listado
    assert len(await store.list("canvas-1")) == 0

    # Ahora otra sesión puede adquirirlo de inmediato
    beto = LockHolder(session_id="s2", user_id="u2", display_name="Beto")
    res = await store.acquire("canvas-1", "elem-1", beto)
    assert res.granted is True


@pytest.mark.anyio
async def test_force_release_elemento_sin_lock_es_noop_devuelve_false(store: LockStore) -> None:
    """force_release sobre elemento o lienzo inexistente es un no-op que devuelve False."""
    assert await store.force_release("canvas-1", "elem-inexistente") is False
    assert await store.force_release("canvas-inexistente", "elem-1") is False


@pytest.mark.anyio
async def test_force_release_no_afecta_otros_elementos_ni_otros_lienzos(
    store: LockStore, clock: ControllableClock
) -> None:
    """
    force_release solo remueve el elemento indicado sin tocar otros locks en el
    mismo o diferente lienzo.
    """
    s1 = LockHolder(session_id="s1")
    s2 = LockHolder(session_id="s2")

    await store.acquire("canvas-1", "elem-1", s1)
    await store.acquire("canvas-1", "elem-2", s1)
    await store.acquire("canvas-2", "elem-1", s2)

    libero = await store.force_release("canvas-1", "elem-1")
    assert libero is True

    # En canvas-1 solo queda elem-2
    locks_1 = await store.list("canvas-1")
    assert len(locks_1) == 1
    assert locks_1[0].element_id == "elem-2"

    # En canvas-2 elem-1 sigue intacto
    locks_2 = await store.list("canvas-2")
    assert len(locks_2) == 1
    assert locks_2[0].element_id == "elem-1"


@pytest.mark.anyio
async def test_force_release_elemento_vencido_descarta_y_devuelve_false(
    store: LockStore, clock: ControllableClock
) -> None:
    """force_release sobre un lock expirado lo descarta limpiamente y devuelve False."""
    s1 = LockHolder(session_id="s1")
    await store.acquire("canvas-1", "elem-1", s1)

    # Avanza 15.1 s -> vencido
    clock.advance(15.1)
    assert await store.force_release("canvas-1", "elem-1") is False


@pytest.mark.anyio
async def test_release_all_libera_todos_los_locks_de_la_sesion_en_el_lienzo(
    store: LockStore, clock: ControllableClock
) -> None:
    s1 = LockHolder(session_id="s1")
    s2 = LockHolder(session_id="s2")

    await store.acquire("canvas-1", "elem-1", s1)
    await store.acquire("canvas-1", "elem-2", s1)
    await store.acquire("canvas-1", "elem-3", s2)

    liberados = await store.release_all("canvas-1", session_id="s1")
    assert sorted(liberados) == ["elem-1", "elem-2"]

    # elem-3 de s2 sigue intacto
    restantes = await store.list("canvas-1")
    assert len(restantes) == 1
    assert restantes[0].element_id == "elem-3"


@pytest.mark.anyio
async def test_vencimiento_a_los_15_segundos(store: LockStore, clock: ControllableClock) -> None:
    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    await store.acquire("canvas-1", "elem-1", ana)

    # A los 14.9 s sigue vigente
    clock.advance(14.9)
    locks = await store.list("canvas-1")
    assert len(locks) == 1

    # A los 15 s expira automáticamente
    clock.advance(0.1)
    locks_vencidos = await store.list("canvas-1")
    assert len(locks_vencidos) == 0

    # Ahora Beto puede adquirirlo sin conflicto
    beto = LockHolder(session_id="s2", user_id="u2", display_name="Beto")
    res = await store.acquire("canvas-1", "elem-1", beto)
    assert res.granted is True
    assert res.lock is not None
    assert res.lock.holder.session_id == "s2"


@pytest.mark.anyio
async def test_renovacion_antes_de_vencer_extiende_15_segundos_mas(
    store: LockStore, clock: ControllableClock
) -> None:
    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    await store.acquire("canvas-1", "elem-1", ana)

    # Avanza 10 segundos y renueva
    clock.advance(10.0)
    res_renueva = await store.acquire("canvas-1", "elem-1", ana)
    assert res_renueva.granted is True

    # Avanza otros 10 segundos (total 20 s desde el inicio original).
    # Sin renovación habría vencido a los 15 s; con la renovación sigue vivo hasta t=25 s.
    clock.advance(10.0)
    locks = await store.list("canvas-1")
    assert len(locks) == 1

    # Avanza 5.1 s más (total 25.1 s) -> ahora sí vence
    clock.advance(5.1)
    locks_final = await store.list("canvas-1")
    assert len(locks_final) == 0


@pytest.mark.anyio
async def test_tope_de_20_locks_por_sesion_deniega_con_limit(
    store: LockStore, clock: ControllableClock
) -> None:
    holder = LockHolder(session_id="s1")

    # Adquirir exactamente 20 locks distintos
    for i in range(MAX_LOCKS_PER_SESSION):
        res = await store.acquire("canvas-1", f"elem-{i}", holder)
        assert res.granted is True, f"Fallo al adquirir elemento {i}"

    # El elemento 21 debe ser denegado con reason='limit'
    res_excedido = await store.acquire("canvas-1", "elem-extra", holder)
    assert res_excedido.granted is False
    assert res_excedido.reason == "limit"
    assert res_excedido.lock is None

    # Renovar uno existente sí debe estar permitido (no suma a la cuenta)
    res_renovar = await store.acquire("canvas-1", "elem-0", holder)
    assert res_renovar.granted is True

    # Si libera uno, ahora sí puede adquirir el extra
    liberado = await store.release("canvas-1", "elem-0", session_id="s1")
    assert liberado is True

    res_ahora_si = await store.acquire("canvas-1", "elem-extra", holder)
    assert res_ahora_si.granted is True


@pytest.mark.anyio
async def test_aislamiento_entre_lienzos_distintos(
    store: LockStore, clock: ControllableClock
) -> None:
    ana = LockHolder(session_id="s1", display_name="Ana")
    beto = LockHolder(session_id="s2", display_name="Beto")

    # Lock del mismo elemento en dos lienzos distintos por dos personas distintas
    res_c1 = await store.acquire("canvas-A", "elem-1", ana)
    res_c2 = await store.acquire("canvas-B", "elem-1", beto)

    assert res_c1.granted is True
    assert res_c2.granted is True

    # Listar locks es por lienzo
    locks_a = await store.list("canvas-A")
    assert len(locks_a) == 1
    assert locks_a[0].holder.session_id == "s1"

    locks_b = await store.list("canvas-B")
    assert len(locks_b) == 1
    assert locks_b[0].holder.session_id == "s2"


@pytest.mark.anyio
async def test_listar_locks_vigentes_omite_vencidos(
    store: LockStore, clock: ControllableClock
) -> None:
    s1 = LockHolder(session_id="s1")
    await store.acquire("canvas-1", "elem-1", s1)

    clock.advance(5.0)
    await store.acquire("canvas-1", "elem-2", s1)

    # Avanza 10.1 s: elem-1 tiene 15.1 s (vencido), elem-2 tiene 10.1 s (vigente)
    clock.advance(10.1)

    vigentes = await store.list("canvas-1")
    assert len(vigentes) == 1
    assert vigentes[0].element_id == "elem-2"


# ============================================================================================
# Pruebas de Mutación del Almacén de Locks
# ============================================================================================


class _MutantWrongTTL(InMemoryLockStore):
    """Mutante 1: TTL es 10 s en vez de 15 s."""

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        existing = canvas_locks.get(element_id)
        if existing is not None and existing.holder.session_id != holder.session_id:
            from backend_case.app.collaboration.application.ports.lock_store import AcquireResult

            return AcquireResult(granted=False, lock=existing, reason="held")
        from backend_case.app.collaboration.application.ports.lock_store import (
            AcquireResult,
            Lock,
        )

        lock = Lock(element_id=element_id, holder=holder, expires_at=now + 10.0)
        self._locks.setdefault(canvas_id, {})[element_id] = lock
        return AcquireResult(granted=True, lock=lock)


class _MutantNoRenewalExtension(InMemoryLockStore):
    """Mutante 2: Renovar no extiende la fecha de expiración."""

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        existing = canvas_locks.get(element_id)
        from backend_case.app.collaboration.application.ports.lock_store import AcquireResult

        if existing is not None:
            if existing.holder.session_id == holder.session_id:
                return AcquireResult(granted=True, lock=existing)  # NO renueva expires_at
            return AcquireResult(granted=False, lock=existing, reason="held")
        return await super().acquire(canvas_id, element_id, holder)


class _MutantAllowSteal(InMemoryLockStore):
    """Mutante 3: Permite que otra sesión sobrescriba un lock ajeno vigente."""

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        now = self._clock()
        from backend_case.app.collaboration.application.ports.lock_store import (
            AcquireResult,
            Lock,
        )

        lock = Lock(element_id=element_id, holder=holder, expires_at=now + LOCK_TTL_SECONDS)
        self._locks.setdefault(canvas_id, {})[element_id] = lock
        return AcquireResult(granted=True, lock=lock)


class _MutantAllowOthersRelease(InMemoryLockStore):
    """Mutante 4: Permite que cualquier sesión libere un lock ajeno."""

    async def release(self, canvas_id: str, element_id: str, session_id: str) -> bool:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        if element_id in canvas_locks:
            del canvas_locks[element_id]
            return True
        return False


class _MutantNoLimit(InMemoryLockStore):
    """Mutante 5: Sin tope de locks por sesión."""

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        existing = canvas_locks.get(element_id)
        from backend_case.app.collaboration.application.ports.lock_store import (
            AcquireResult,
            Lock,
        )

        if existing is not None and existing.holder.session_id != holder.session_id:
            return AcquireResult(granted=False, lock=existing, reason="held")
        lock = Lock(element_id=element_id, holder=holder, expires_at=now + LOCK_TTL_SECONDS)
        self._locks.setdefault(canvas_id, {})[element_id] = lock
        return AcquireResult(granted=True, lock=lock)


class _MutantLimitOffByOne(InMemoryLockStore):
    """Mutante 6: Permite 21 locks (> en vez de >=)."""

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        now = self._clock()
        canvas_locks = self._clean_expired(canvas_id, now)
        existing = canvas_locks.get(element_id)
        from backend_case.app.collaboration.application.ports.lock_store import (
            AcquireResult,
            Lock,
        )

        if existing is not None:
            if existing.holder.session_id == holder.session_id:
                renewed = Lock(
                    element_id=element_id,
                    holder=holder,
                    expires_at=now + LOCK_TTL_SECONDS,
                )
                self._locks.setdefault(canvas_id, {})[element_id] = renewed
                return AcquireResult(granted=True, lock=renewed)
            return AcquireResult(granted=False, lock=existing, reason="held")

        count = sum(1 for lk in canvas_locks.values() if lk.holder.session_id == holder.session_id)
        if count > MAX_LOCKS_PER_SESSION:  # Mutación: permite 21 (debería ser >=)
            return AcquireResult(granted=False, lock=None, reason="limit")

        new_lock = Lock(element_id=element_id, holder=holder, expires_at=now + LOCK_TTL_SECONDS)
        self._locks.setdefault(canvas_id, {})[element_id] = new_lock
        return AcquireResult(granted=True, lock=new_lock)


class _MutantReleaseAllClearsOthers(InMemoryLockStore):
    """Mutante 7: release_all borra todos los locks del lienzo sin filtrar por sesión."""

    async def release_all(self, canvas_id: str, session_id: str) -> list[str]:
        canvas_locks = self._locks.get(canvas_id, {})
        cleared = list(canvas_locks.keys())
        self._locks.pop(canvas_id, None)
        return cleared


class _MutantListReturnsExpired(InMemoryLockStore):
    """Mutante 8: list() no purga y devuelve locks vencidos."""

    async def list(self, canvas_id: str) -> list[Any]:
        return list(self._locks.get(canvas_id, {}).values())


class _MutantCrossCanvasLeak(InMemoryLockStore):
    """Mutante 9: Ignora canvas_id y almacena todo en un único lienzo global."""

    def __init__(self, clock: Any) -> None:
        super().__init__(clock=clock)
        self._global_canvas = "SHARED_CANVAS"

    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> Any:
        return await super().acquire(self._global_canvas, element_id, holder)

    async def list(self, canvas_id: str) -> list[Any]:
        return await super().list(self._global_canvas)


class _MutantForceReleaseNoOp(InMemoryLockStore):
    """Mutante 10: force_release no elimina el lock y devuelve False."""

    async def force_release(self, canvas_id: str, element_id: str) -> bool:
        return False


MUTANTS = [
    ("Wrong TTL", _MutantWrongTTL),
    ("No Renewal Extension", _MutantNoRenewalExtension),
    ("Allow Steal", _MutantAllowSteal),
    ("Allow Others Release", _MutantAllowOthersRelease),
    ("No Limit", _MutantNoLimit),
    ("Limit Off By One", _MutantLimitOffByOne),
    ("Release All Clears Others", _MutantReleaseAllClearsOthers),
    ("List Returns Expired", _MutantListReturnsExpired),
    ("Cross Canvas Leak", _MutantCrossCanvasLeak),
    ("Force Release NoOp", _MutantForceReleaseNoOp),
]


@pytest.mark.anyio
@pytest.mark.parametrize("name,mutant_cls", MUTANTS)
async def test_mutantes_memory_lock_store_son_detectados(
    name: str, mutant_cls: type[InMemoryLockStore]
) -> None:
    """Verifica que cada uno de los mutantes rompa al menos una aserción del contrato."""
    test_suite = [
        test_adquirir_lock_exitoso,
        test_renovar_lock_idempotente_mismo_titular_extiende_expiracion,
        test_rechazo_held_cuando_otra_sesion_lo_tiene_vigente,
        test_liberar_exitoso_solo_para_el_titular_real,
        test_force_release_libera_lock_sin_importar_titular,
        test_release_all_libera_todos_los_locks_de_la_sesion_en_el_lienzo,
        test_vencimiento_a_los_15_segundos,
        test_renovacion_antes_de_vencer_extiende_15_segundos_mas,
        test_tope_de_20_locks_por_sesion_deniega_con_limit,
        test_aislamiento_entre_lienzos_distintos,
        test_listar_locks_vigentes_omite_vencidos,
    ]

    detected = False
    for test_fn in test_suite:
        # Reset reloj y tienda mutante
        clock = ControllableClock()
        store = mutant_cls(clock=clock)
        try:
            await test_fn(store, clock)
        except (AssertionError, Exception):
            detected = True
            break

    assert detected is True, f"El mutante '{name}' NO fue detectado por la suite de pruebas."


@pytest.mark.anyio
async def test_acquire_concurrente_mismo_elemento_exactamente_uno_gana() -> None:
    """Carrera real: dos sesiones intentan adquirir a la vez el mismo elemento sobre Redis."""
    import asyncio

    import fakeredis
    import fakeredis.aioredis as fake_aioredis

    from backend_case.app.collaboration.infrastructure.redis_lock_store import RedisLockStore

    server = fakeredis.FakeServer()
    r1 = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    r2 = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    store1 = RedisLockStore(redis_client=r1)
    store2 = RedisLockStore(redis_client=r2)

    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    beto = LockHolder(session_id="s2", user_id="u2", display_name="Beto")

    res_ana, res_beto = await asyncio.gather(
        store1.acquire("canvas-1", "elem-1", ana),
        store2.acquire("canvas-1", "elem-1", beto),
    )

    assert (res_ana.granted and not res_beto.granted) or (res_beto.granted and not res_ana.granted)
    ganador = res_ana if res_ana.granted else res_beto
    perdedor = res_beto if res_ana.granted else res_ana

    assert ganador.granted is True
    assert ganador.reason is None
    assert ganador.lock is not None
    assert perdedor.granted is False
    assert perdedor.reason == "held"
    assert perdedor.lock is not None
    assert perdedor.lock.holder.session_id == ganador.lock.holder.session_id


@pytest.mark.anyio
async def test_acquire_concurrente_limite_20_locks_un_solo_ganador() -> None:
    """Carrera real: sesión con 19 locks intenta adquirir 2 a la vez; exactamente uno entra."""
    import asyncio

    import fakeredis
    import fakeredis.aioredis as fake_aioredis

    from backend_case.app.collaboration.infrastructure.redis_lock_store import RedisLockStore

    server = fakeredis.FakeServer()
    r1 = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    r2 = fake_aioredis.FakeRedis(server=server, decode_responses=True)
    store1 = RedisLockStore(redis_client=r1)
    store2 = RedisLockStore(redis_client=r2)

    ana = LockHolder(session_id="s1", user_id="u1", display_name="Ana")
    for i in range(19):
        await store1.acquire("canvas-1", f"elem-pre-{i}", ana)

    res_a, res_b = await asyncio.gather(
        store1.acquire("canvas-1", "elem-20", ana),
        store2.acquire("canvas-1", "elem-21", ana),
    )

    assert (res_a.granted and not res_b.granted) or (res_b.granted and not res_a.granted)
    ganador = res_a if res_a.granted else res_b
    perdedor = res_b if res_a.granted else res_a

    assert ganador.granted is True
    assert perdedor.granted is False
    assert perdedor.reason == "limit"
    assert perdedor.lock is None

    locks = await store1.list("canvas-1")
    assert len(locks) == 20
