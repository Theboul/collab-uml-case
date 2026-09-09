import copy
import uuid
from datetime import datetime, timezone
from typing import Any, NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend_case.app.application.mappers import (
    DomainToPydanticMapper,
    PydanticToDomainMapper,
)
from backend_case.app.schemas.uml import UmlModelSchema
from core.uml_domain.exceptions import (
    CanvasNoEncontrado,
    ConcurrentEditConflict,
    UmlDomainError,
)
from core.uml_domain.model import Lienzo

from .db_models import CanvasCollaboratorORM, CanvasORM


class CanvasResult(NamedTuple):
    lienzo: Lienzo
    version: int
    owner_id: str | None = None
    room_name: str | None = None
    role: str = "ANFITRION"


def _needs_parameter_normalization(semantic_model: dict[str, Any]) -> bool:
    classes = semantic_model.get("classes", [])
    for c in classes:
        ops_list = list(c.get("methods", [])) + list(c.get("operations", []))
        for op in ops_list:
            parameters = op.get("parameters", [])
            for p in parameters:
                if not p.get("id"):
                    return True
    return False


def _normalize_parameters_in_dict(semantic_model: dict[str, Any]) -> dict[str, Any]:
    data = copy.deepcopy(semantic_model)
    for c in data.get("classes", []):
        for op in c.get("methods", []):
            for p in op.get("parameters", []):
                if not p.get("id"):
                    p["id"] = str(uuid.uuid4())
        for op in c.get("operations", []):
            for p in op.get("parameters", []):
                if not p.get("id"):
                    p["id"] = str(uuid.uuid4())
    return data


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

    async def guardar_atomico(
        self,
        canvas_id: str,
        expected_version: int,
        lienzo: Lienzo,
    ) -> CanvasResult:
        """
        Actualiza un lienzo de forma atómica comprobando que su versión coincida con expected_version.
        Si la versión difiere o no existe, lanza ConcurrentEditConflict o CanvasNoEncontrado.
        """
        model_schema = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo)
        semantic_model_data = model_schema.model_dump(mode="json")

        stmt = (
            update(CanvasORM)
            .where(CanvasORM.id == canvas_id, CanvasORM.version == expected_version)
            .values(
                name=lienzo.modelo.name,
                description=lienzo.modelo.description,
                version=CanvasORM.version + 1,
                semantic_model=semantic_model_data,
                visual_layout=lienzo.visual_layout,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(CanvasORM.version, CanvasORM.owner_id, CanvasORM.room_name)
        )
        result = await self.session.execute(stmt)
        row = result.first()
        if row is None:
            check_stmt = select(CanvasORM.version).where(CanvasORM.id == canvas_id)
            check_res = await self.session.execute(check_stmt)
            existing_version = check_res.scalar_one_or_none()
            if existing_version is None:
                raise CanvasNoEncontrado(f"Lienzo con ID '{canvas_id}' no encontrado.")
            else:
                raise ConcurrentEditConflict(
                    f"Conflicto de versión al actualizar lienzo '{canvas_id}'. "
                    f"Versión esperada: {expected_version}, versión actual en base de datos: {existing_version}."
                )

        new_version, owner_id, room_name = row
        await self.session.flush()
        return CanvasResult(
            lienzo=lienzo,
            version=new_version,
            owner_id=owner_id,
            room_name=room_name,
        )

    async def _asegurar_normalizacion_parametros(self, canvas_orm: CanvasORM) -> CanvasORM:
        if not isinstance(canvas_orm.semantic_model, dict):
            return canvas_orm
        if not _needs_parameter_normalization(canvas_orm.semantic_model):
            return canvas_orm

        canvas_id = canvas_orm.id
        max_retries = 3
        for _ in range(max_retries):
            normalized_data = _normalize_parameters_in_dict(canvas_orm.semantic_model)
            current_version = canvas_orm.version
            stmt_cas = (
                update(CanvasORM)
                .where(CanvasORM.id == canvas_id, CanvasORM.version == current_version)
                .values(
                    semantic_model=normalized_data,
                    version=CanvasORM.version + 1,
                    updated_at=datetime.now(timezone.utc),
                )
                .returning(CanvasORM.version)
            )
            cas_res = await self.session.execute(stmt_cas)
            if cas_res.first() is not None:
                await self.session.commit()
                stmt_reload = select(CanvasORM).where(CanvasORM.id == canvas_id)
                reload_res = await self.session.execute(stmt_reload)
                return reload_res.scalar_one()
            else:
                await self.session.rollback()
                stmt_reload = select(CanvasORM).where(CanvasORM.id == canvas_id)
                reload_res = await self.session.execute(stmt_reload)
                canvas_orm = reload_res.scalar_one_or_none()
                if canvas_orm is None:
                    raise CanvasNoEncontrado(f"Lienzo con ID '{canvas_id}' no encontrado.")
                if not _needs_parameter_normalization(canvas_orm.semantic_model):
                    return canvas_orm

        # Agotados los 3 intentos:
        stmt_reload = select(CanvasORM).where(CanvasORM.id == canvas_id)
        reload_res = await self.session.execute(stmt_reload)
        canvas_orm = reload_res.scalar_one_or_none()
        if canvas_orm is None:
            raise CanvasNoEncontrado(f"Lienzo con ID '{canvas_id}' no encontrado.")
        if _needs_parameter_normalization(canvas_orm.semantic_model):
            raise UmlDomainError(
                "No se pudo normalizar los identificadores de parámetros históricos tras varios intentos por contención concurrente. Por favor, intente nuevamente."
            )
        return canvas_orm

    async def obtener(self, canvas_id: str) -> CanvasResult:
        """
        Recupera un Lienzo, su versión, anfitrión y sala por su ID o lanza CanvasNoEncontrado.
        Normaliza preventivamente parámetros históricos sin ID si existen.
        """
        stmt = select(CanvasORM).where(CanvasORM.id == canvas_id)
        result = await self.session.execute(stmt)
        canvas_orm = result.scalar_one_or_none()

        if canvas_orm is None:
            raise CanvasNoEncontrado(f"Lienzo con ID '{canvas_id}' no encontrado.")

        canvas_orm = await self._asegurar_normalizacion_parametros(canvas_orm)

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

        canvas_orm = await self._asegurar_normalizacion_parametros(canvas_orm)

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

    async def es_colaborador(self, canvas_id: str, user_id: str) -> bool:
        """
        Verifica si un usuario está registrado como colaborador del lienzo.
        """
        stmt = select(CanvasCollaboratorORM).where(
            CanvasCollaboratorORM.canvas_id == canvas_id,
            CanvasCollaboratorORM.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def agregar_colaborador(self, canvas_id: str, user_id: str) -> None:
        """
        Registra la participación de un colaborador en el lienzo si aún no existe.
        La PK compuesta (canvas_id, user_id) asegura la unicidad transaccional.
        """
        if not await self.es_colaborador(canvas_id, user_id):
            collab = CanvasCollaboratorORM(
                canvas_id=canvas_id,
                user_id=user_id,
                joined_at=datetime.now(timezone.utc),
            )
            self.session.add(collab)
            await self.session.flush()

    async def resolver_rol(self, canvas_id: str, owner_id: str | None, user_id: str | None) -> str:
        """
        Resuelve dinámicamente el rol del usuario para el lienzo (ANFITRION, COLABORADOR o INVITADO).
        """
        if not user_id:
            return "INVITADO"
        if owner_id and owner_id == user_id:
            return "ANFITRION"
        if await self.es_colaborador(canvas_id, user_id):
            return "COLABORADOR"
        return "INVITADO"

    async def buscar_por_codigo_acceso(self, access_code: str) -> CanvasORM | None:
        """
        Busca un lienzo normalizando el código de acceso (espacios, mayúsculas y prefijo room-).
        """
        code = access_code.strip()
        variations = [code, code.lower()]
        if not code.lower().startswith("room-"):
            variations.extend([f"room-{code}", f"room-{code.lower()}"])
        else:
            variations.append(code[5:])

        for var in variations:
            stmt = select(CanvasORM).where(CanvasORM.room_name == var)
            res = await self.session.execute(stmt)
            canvas = res.scalar_one_or_none()
            if canvas is not None:
                return canvas
        return None

