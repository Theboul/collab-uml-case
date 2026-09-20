"""Acceso a la Sala y servicios de colaboración del proceso, igual para rutas HTTP y WebSocket."""

from typing import Annotated

from fastapi import Depends
from fastapi.requests import HTTPConnection

from .application.collaboration_service import CollaborationService
from .application.ports.collaboration_room import CollaborationRoom
from .application.ports.lock_store import LockStore
from .application.presence_service import PresenceService


def get_collaboration_room(connection: HTTPConnection) -> CollaborationRoom:
    room: CollaborationRoom = connection.app.state.collaboration_room
    return room


def get_lock_store(connection: HTTPConnection) -> LockStore:
    store: LockStore = connection.app.state.lock_store
    return store


def get_presence_service(connection: HTTPConnection) -> PresenceService:
    service: PresenceService = connection.app.state.presence_service
    return service


def get_collaboration_service(
    room: Annotated[CollaborationRoom, Depends(get_collaboration_room)],
    lock_store: Annotated[LockStore, Depends(get_lock_store)],
    presence_service: Annotated[PresenceService, Depends(get_presence_service)],
) -> CollaborationService:
    return CollaborationService(room, lock_store, presence_service)


CollaborationRoomDep = Annotated[CollaborationRoom, Depends(get_collaboration_room)]
LockStoreDep = Annotated[LockStore, Depends(get_lock_store)]
PresenceServiceDep = Annotated[PresenceService, Depends(get_presence_service)]
CollaborationServiceDep = Annotated[CollaborationService, Depends(get_collaboration_service)]
