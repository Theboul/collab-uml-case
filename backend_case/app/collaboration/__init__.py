"""
Módulo de colaboración en tiempo real (PA2 / CU5).
Gestiona la concurrencia granular, presencia y control de conflictos sobre el lienzo UML.
"""

from .application.collaboration_service import CollaborationService
from .application.ports.collaboration_room import CollaborationRoom
from .application.ports.lock_store import LockStore
from .application.presence_service import PresenceService
from .infrastructure.memory_lock_store import InMemoryLockStore
from .infrastructure.memory_room import InMemoryCollaborationRoom
from .ws_router import collaboration_ws_router


def create_collaboration_room() -> CollaborationRoom:
    """Sala del proceso. Hoy siempre en memoria; el Paso 6 elegirá según REDIS_URL."""
    return InMemoryCollaborationRoom()


def create_lock_store() -> LockStore:
    """Almacén de locks del proceso (en memoria)."""
    return InMemoryLockStore()


def create_presence_service() -> PresenceService:
    """Servicio de presencia de sesiones (en memoria)."""
    return PresenceService()


__all__ = [
    "CollaborationService",
    "collaboration_ws_router",
    "create_collaboration_room",
    "create_lock_store",
    "create_presence_service",
]
