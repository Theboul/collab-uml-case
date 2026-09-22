"""Esquema de un Lienzo completo: respuestas HTTP e instantánea que se difunde en vivo."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.application.mappers import DomainToPydanticMapper
from backend_case.app.schemas.uml import UmlModelSchema
from core.uml_domain.model import Lienzo


class CanvasSummarySchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    version: int
    ownerId: str | None = None
    roomName: str | None = None
    owner_id: str | None = None
    room_name: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


def to_summary_schema(item: dict[str, Any]) -> CanvasSummarySchema:
    owner_id = item.get("owner_id") or item.get("ownerId")
    room_name = item.get("room_name") or item.get("roomName")
    return CanvasSummarySchema(
        id=str(item["id"]),
        name=str(item["name"]),
        description=item.get("description"),
        version=int(item["version"]),
        ownerId=owner_id,
        roomName=room_name,
        owner_id=owner_id,
        room_name=room_name,
        created_at=item.get("created_at"),
        updated_at=item.get("updated_at"),
    )


class CanvasDetailSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    version: int
    ownerId: str | None = None
    roomName: str | None = None
    owner_id: str | None = None
    room_name: str | None = None
    role: str = "ANFITRION"
    visualLayout: dict[str, Any] = Field(default_factory=dict)
    model: UmlModelSchema


def to_detail_schema(
    lienzo: Lienzo,
    version: int,
    owner_id: str | None = None,
    room_name: str | None = None,
    role: str = "ANFITRION",
) -> CanvasDetailSchema:
    model_schema = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo)
    return CanvasDetailSchema(
        id=lienzo.id,
        name=lienzo.modelo.name,
        description=lienzo.modelo.description,
        version=version,
        ownerId=owner_id,
        roomName=room_name,
        owner_id=owner_id,
        room_name=room_name,
        role=role,
        visualLayout=lienzo.visual_layout,
        model=model_schema,
    )
