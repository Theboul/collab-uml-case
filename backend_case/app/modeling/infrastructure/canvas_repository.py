"""
Repositorio de infraestructura para la persistencia del agregado Lienzo usando SQLAlchemy Async.
"""

from datetime import datetime, timezone

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


class CanvasRepository:
    """
    Repositorio de persistencia relacional/JSONB para el agregado Lienzo.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def guardar(self, lienzo: Lienzo) -> Lienzo:
        """
        Persiste o actualiza un Lienzo en la base de datos.
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
            canvas_orm.semantic_model = semantic_model_data
            canvas_orm.visual_layout = lienzo.visual_layout
            canvas_orm.updated_at = datetime.now(timezone.utc)
        else:
            canvas_orm = CanvasORM(
                id=lienzo.id,
                name=lienzo.modelo.name,
                description=lienzo.modelo.description,
                version=1,
                semantic_model=semantic_model_data,
                visual_layout=lienzo.visual_layout,
            )
            self.session.add(canvas_orm)

        await self.session.flush()
        return lienzo, canvas_orm.version

    async def obtener(self, canvas_id: str) -> tuple[Lienzo, int]:
        """
        Recupera un Lienzo y su versión por su ID o lanza CanvasNoEncontrado.
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
        return lienzo, canvas_orm.version

    async def listar(self) -> list[dict]:
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
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            }
            for c in canvases
        ]
