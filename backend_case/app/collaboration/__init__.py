"""
Módulo de colaboración en tiempo real (PA2 / CU5).
Gestiona la concurrencia granular, presencia y control de conflictos sobre el lienzo UML.
"""

from .ws_router import collaboration_ws_router

__all__ = ["collaboration_ws_router"]
