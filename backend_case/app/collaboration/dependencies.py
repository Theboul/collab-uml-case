"""Acceso a la Sala de colaboración del proceso, igual para rutas HTTP y WebSocket."""

from typing import Annotated

from fastapi import Depends
from fastapi.requests import HTTPConnection

from .application.ports.collaboration_room import CollaborationRoom


def get_collaboration_room(connection: HTTPConnection) -> CollaborationRoom:
    room: CollaborationRoom = connection.app.state.collaboration_room
    return room


CollaborationRoomDep = Annotated[CollaborationRoom, Depends(get_collaboration_room)]
