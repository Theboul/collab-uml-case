"""
Rutas API v2 para el módulo de modelado UML (CU1 - CU4).
"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.application.mappers import DomainToPydanticMapper
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.schemas.uml import UmlModelSchema
from backend_case.app.shared.deps import get_canvas_service
from backend_case.app.shared.security.dependencies import get_current_user_optional
from backend_case.app.shared.security.models import UserORM
from core.uml_domain.model import Lienzo

router = APIRouter(prefix="/canvases", tags=["modeling"])

CanvasServiceDep = Annotated[CanvasService, Depends(get_canvas_service)]
CurrentUserOptionalDep = Annotated[UserORM | None, Depends(get_current_user_optional)]


# ---------------------------------------------------------------------------
# DTOs de Frontera HTTP
# ---------------------------------------------------------------------------

class CreateCanvasRequest(BaseModel):
    name: str = Field(default="Diagrama Sin Título", max_length=255)
    description: str | None = None


class AddClassRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=255)
    isAbstract: bool = Field(default=False)


class AddAssociationRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sourceClassId: str = Field(..., description="ID del clasificador origen")
    targetClassId: str = Field(..., description="ID del clasificador destino")
    name: str | None = None
    sourceRole: str | None = None
    targetRole: str | None = None
    sourceMultiplicity: str = Field(default="1")
    targetMultiplicity: str = Field(default="1")
    sourceAggregation: str = Field(default="none")
    targetAggregation: str = Field(default="none")


class EditorCommandRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    operationId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    expectedVersion: int
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


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
    visualLayout: dict[str, Any] = Field(default_factory=dict)
    model: UmlModelSchema


class CommandResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accepted: bool = True
    version: int
    operationId: str | None = None
    canvas: CanvasDetailSchema | None = None


def _to_detail_schema(
    lienzo: Lienzo,
    version: int,
    owner_id: str | None = None,
    room_name: str | None = None,
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
        visualLayout=lienzo.visual_layout,
        model=model_schema,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CanvasSummarySchema])
async def list_canvases(
    service: CanvasServiceDep,
):
    """
    Lista todos los lienzos de modelado registrados.
    """
    return await service.listar_lienzos()


@router.post("", response_model=CanvasDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_canvas(
    payload: CreateCanvasRequest,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
):
    """
    CU1: Crear un nuevo lienzo UML persistido con usuario anfitrión y sala única.
    """
    owner_id = current_user.id if current_user else None
    res = await service.crear_lienzo(
        nombre=payload.name,
        descripcion=payload.description,
        owner_id=owner_id,
    )
    return _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name)


@router.get("/by-room/{room_name}", response_model=CanvasDetailSchema)
async def get_canvas_by_room(
    room_name: str,
    service: CanvasServiceDep,
):
    """
    Recupera un lienzo por su mecanismo de acceso (room_name).
    """
    res = await service.obtener_por_room_name(room_name)
    return _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name)


@router.get("/{canvas_id}", response_model=CanvasDetailSchema)
async def get_canvas(
    canvas_id: str,
    service: CanvasServiceDep,
):
    """
    CU2 / CU3: Obtener un lienzo y su modelo UML persistido.
    """
    res = await service.obtener_lienzo(canvas_id)
    return _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name)


@router.post("/{canvas_id}/commands", response_model=CommandResponse)
async def execute_editor_command(
    canvas_id: str,
    command: EditorCommandRequest,
    service: CanvasServiceDep,
):
    """
    Ejecuta un comando del editor sobre el lienzo con control de versión optimista.
    """
    res = await service.ejecutar_comando(
        canvas_id=canvas_id,
        operation_id=command.operationId,
        expected_version=command.expectedVersion,
        cmd_type=command.type,
        payload=command.payload,
    )
    return CommandResponse(
        accepted=True,
        version=res.version,
        operationId=command.operationId,
        canvas=_to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name),
    )


@router.post("/{canvas_id}/classes", response_model=CanvasDetailSchema, status_code=status.HTTP_201_CREATED)
async def add_class(
    canvas_id: str,
    payload: AddClassRequest,
    service: CanvasServiceDep,
):
    """
    CU3: Agregar una clase al modelo del lienzo.
    """
    lienzo, version, _, _ = await service.agregar_clase(
        canvas_id=canvas_id,
        nombre=payload.name,
        is_abstract=payload.isAbstract,
    )
    return _to_detail_schema(lienzo, version)


@router.post("/{canvas_id}/associations", response_model=CanvasDetailSchema, status_code=status.HTTP_201_CREATED)
async def add_association(
    canvas_id: str,
    payload: AddAssociationRequest,
    service: CanvasServiceDep,
):
    """
    CU4: Agregar una asociación binaria entre dos clases en el lienzo.
    """
    lienzo, version, _, _ = await service.agregar_asociacion(
        canvas_id=canvas_id,
        origen_id=payload.sourceClassId,
        destino_id=payload.targetClassId,
        nombre=payload.name,
        rol_origen=payload.sourceRole,
        rol_destino=payload.targetRole,
        multiplicidad_origen=payload.sourceMultiplicity,
        multiplicidad_destino=payload.targetMultiplicity,
        agregacion_origen=payload.sourceAggregation,
        agregacion_destino=payload.targetAggregation,
    )
    return _to_detail_schema(lienzo, version)

