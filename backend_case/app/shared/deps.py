"""
Inyección de dependencias transversal para FastAPI.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend_case.app.collaboration.dependencies import (
    CollaborationRoomDep,
    LockStoreDep,
)
from backend_case.app.collaboration.infrastructure.canvas_change_publisher import (
    CollaborationChangePublisher,
)
from backend_case.app.generation.application.generation_service import GenerationService
from backend_case.app.generation.infrastructure.spring.http_spring_adapter import (
    HttpSpringAdapter,
)
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from backend_case.app.shared.db.base import get_db_session


def get_canvas_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    room: CollaborationRoomDep,
    lock_store: LockStoreDep,
) -> CanvasService:
    """
    Inyecta una instancia de CanvasService con el repositorio configurado sobre la sesión actual
    y el publicador que avisa a la Sala de los cambios ya confirmados.
    """
    repository = CanvasRepository(session)
    return CanvasService(repository, CollaborationChangePublisher(room, lock_store))


def get_generation_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> GenerationService:
    """
    Inyecta GenerationService (CU10) con su propia CanvasService (misma sesión)
    y el adaptador HTTP real hacia el generador Spring Boot (back_generator_uml).
    """
    repository = CanvasRepository(session)
    canvas_service = CanvasService(repository)
    return GenerationService(canvas_service, HttpSpringAdapter())
