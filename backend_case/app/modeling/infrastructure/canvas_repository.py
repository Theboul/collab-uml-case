import uuid
from datetime import datetime, timezone
from typing import Any, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend_case.app.application.mappers import (
    DomainToPydanticMapper,
    PydanticToDomainMapper,
)
from backend_case.app.schemas.uml import UmlModelSchema
from core.uml_domain.exceptions import CanvasNoEncontrado
from core.uml_domain.model import Lienzo

from .db_models import CanvasORM


class CanvasResult(NamedTuple):
    lienzo: Lienzo
    version: int
    owner_id: str | None = None
    room_name: str | None = None


class CanvasRepository:
    """
    Repositorio de persistencia relacional/JSONB para el agregado Lienzo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def guardar(
        self,
        lienzo: Lienzo,
        owner_id: str | None = None,
        room_name: str | None = None,
    ) -> CanvasResult:
        """
        Persiste o actualiza un Lienzo en la base de datos dentro de la transacción activa.
        """
        model_schema = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo)
        semantic_model_data = model_schema.model_dump(mode="json")

        stmt = select(CanvasORM).where(CanvasORM.id == lienzo.id)
        result = await self.session.execute(stmt)
        canvas_orm = result.scalar_one_or_none()

        if canvas_orm is not None:
            canvas_orm.name = lienzo.modelo.name
            canvas_orm.description = lienzo.modelo.description
            canvas_orm.version = canvas_orm.version + 1
            if owner_id is not None:
                canvas_orm.owner_id = owner_id
            if room_name is not None and not canvas_orm.room_name:
                canvas_orm.room_name = room_name
            canvas_orm.semantic_model = semantic_model_data
            canvas_orm.visual_layout = lienzo.visual_layout
            canvas_orm.updated_at = datetime.now(timezone.utc)
        else:
            final_room = room_name or f"room-{uuid.uuid4().hex[:8]}"
            default_layout = {
                "viewport": {"zoom": 1, "panX": 0, "panY": 0},
                "nodes": {},
                "links": {},
            }
            canvas_orm = CanvasORM(
                id=lienzo.id,
                name=lienzo.modelo.name,
                description=lienzo.modelo.description,
                version=1,
                owner_id=owner_id,
                room_name=final_room,
                semantic_model=semantic_model_data,
                visual_layout=lienzo.visual_layout if lienzo.visual_layout else default_layout,
            )
            self.session.add(canvas_orm)

        await self.session.flush()
        return CanvasResult(
            lienzo=lienzo,
            version=canvas_orm.version,
            owner_id=canvas_orm.owner_id,
            room_name=canvas_orm.room_name,
        )

    async def obtener(self, canvas_id: str) -> CanvasResult:
        """
        Recupera un Lienzo, su versión, anfitrión y sala por su ID o lanza CanvasNoEncontrado.
        """
        stmt = select(CanvasORM).where(CanvasORM.id == canvas_id)
        result = await self.session.execute(stmt)
        canvas_orm = result.scalar_one_or_none()

        if canvas_orm is None:
            raise CanvasNoEncontrado(f"Lienzo con ID '{canvas_id}' no encontrado.")

        schema = UmlModelSchema.model_validate(canvas_orm.semantic_model)
        domain_model = PydanticToDomainMapper.to_domain_model(schema)

        lienzo = Lienzo(
            modelo=domain_model,
            visual_layout=canvas_orm.visual_layout or {},
            creado_en=canvas_orm.created_at or datetime.now(timezone.utc),
        )
        return CanvasResult(
            lienzo=lienzo,
            version=canvas_orm.version,
            owner_id=canvas_orm.owner_id,
            room_name=canvas_orm.room_name,
        )

    async def obtener_por_room_name(self, room_name: str) -> CanvasResult:
        """
        Recupera un Lienzo a través de su código o mecanismo de acceso room_name.
        """
        stmt = select(CanvasORM).where(CanvasORM.room_name == room_name)
        result = await self.session.execute(stmt)
        canvas_orm = result.scalar_one_or_none()

        if canvas_orm is None:
            raise CanvasNoEncontrado(f"Lienzo con sala '{room_name}' no encontrado.")

        schema = UmlModelSchema.model_validate(canvas_orm.semantic_model)
        domain_model = PydanticToDomainMapper.to_domain_model(schema)

        lienzo = Lienzo(
            modelo=domain_model,
            visual_layout=canvas_orm.visual_layout or {},
            creado_en=canvas_orm.created_at or datetime.now(timezone.utc),
        )
        return CanvasResult(
            lienzo=lienzo,
            version=canvas_orm.version,
            owner_id=canvas_orm.owner_id,
            room_name=canvas_orm.room_name,
        )

    async def listar(self) -> list[dict[str, Any]]:
        """
        Lista resúmenes de los lienzos existentes.
        """
        stmt = select(CanvasORM).order_by(CanvasORM.updated_at.desc())
        result = await self.session.execute(stmt)
        canvases = result.scalars().all()
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "version": c.version,
                "owner_id": c.owner_id,
                "room_name": c.room_name,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in canvases
        ]
