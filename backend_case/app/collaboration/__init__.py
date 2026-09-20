"""
Módulo de colaboración en tiempo real (PA2 / CU5).
Gestiona la concurrencia granular, presencia y control de conflictos sobre el lienzo UML.
"""

from .application.ports.collaboration_room import CollaborationRoom
from .infrastructure.memory_room import InMemoryCollaborationRoom
from .ws_router import collaboration_ws_router


def create_collaboration_room() -> CollaborationRoom:
    """Sala del proceso. Hoy siempre en memoria; el Paso 6 elegirá según REDIS_URL."""
    return InMemoryCollaborationRoom()


__all__ = ["collaboration_ws_router", "create_collaboration_room"]
