"""
Puerto del almacén de locks por elemento (ADR-0003 y su Addendum).

Advisory: solo informa y coordina la edición concurrente de elementos.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

LOCK_TTL_SECONDS = 15
MAX_LOCKS_PER_SESSION = 20


@dataclass(frozen=True)
class LockHolder:
    session_id: str
    user_id: str | None = None
    display_name: str | None = None


@dataclass(frozen=True)
class Lock:
    element_id: str
    holder: LockHolder
    expires_at: float


@dataclass(frozen=True)
class AcquireResult:
    granted: bool
    lock: Lock | None
    reason: Literal["held", "limit"] | None = None


class LockStore(Protocol):
    async def acquire(self, canvas_id: str, element_id: str, holder: LockHolder) -> AcquireResult:
        """
        Adquiere o renueva (idempotente para el mismo titular) el lock de un elemento.
        Si otra sesión ya lo tiene vigente, deniega con reason='held' y el lock actual.
        Si la sesión supera el tope de locks (MAX_LOCKS_PER_SESSION), deniega con reason='limit'.
        """
        ...

    async def release(self, canvas_id: str, element_id: str, session_id: str) -> bool:
        """
        Libera el lock solo si session_id es el titular vigente.
        Devuelve True si liberó un lock activo, False si no existía o pertenecía a otra sesión.
        """
        ...

    async def release_all(self, canvas_id: str, session_id: str) -> list[str]:
        """
        Libera todos los locks vigentes de la sesión en el lienzo (al salir o desconectarse).
        Devuelve la lista de element_ids liberados.
        """
        ...

    async def list(self, canvas_id: str) -> list[Lock]:
        """
        Lista todos los locks vigentes del lienzo (los vencidos se descartan).
        """
        ...
