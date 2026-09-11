"""
Rutas API v2 para el módulo de modelado UML (CU1 - CU4).
"""
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.application.mappers import DomainToPydanticMapper
from backend_case.app.collaboration.room_registry import collaboration_room_registry
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


class JoinCanvasRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accessCode: str = Field(..., min_length=1, description="Código de sala o enlace de invitación")


class JoinCanvasResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    workspaceId: str
    canvasId: str
    roomName: str
    role: str
    joined: bool


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
    role: str = "ANFITRION"
    visualLayout: dict[str, Any] = Field(default_factory=dict)
    model: UmlModelSchema


class CommandResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    accepted: bool = True
    version: int
    operationId: str | None = None
    canvas: CanvasDetailSchema | None = None
    undoPayload: dict[str, Any] | None = None


def _to_detail_schema(
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


@router.post("/join", response_model=JoinCanvasResponse)
async def join_canvas(
    payload: JoinCanvasRequest,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
):
    """
    CU2: Unirse a un lienzo UML existente mediante código o enlace de invitación.
    """
    user_id = current_user.id if current_user else "anonymous-user"
    res = await service.unirse_a_lienzo(access_code=payload.accessCode, user_id=user_id)
    return JoinCanvasResponse(
        workspaceId=res["workspaceId"],
        canvasId=res["canvasId"],
        roomName=res["roomName"],
        role=res["role"],
        joined=res["joined"],
    )


@router.get("/by-room/{room_name}", response_model=CanvasDetailSchema)
async def get_canvas_by_room(
    room_name: str,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
):
    """
    Recupera un lienzo por su mecanismo de acceso (room_name) y resuelve el rol del participante.
    """
    user_id = current_user.id if current_user else None
    res = await service.obtener_por_room_name(room_name, user_id=user_id)
    return _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name, res.role)


@router.get("/{canvas_id}", response_model=CanvasDetailSchema)
async def get_canvas(
    canvas_id: str,
    service: CanvasServiceDep,
    current_user: CurrentUserOptionalDep = None,
):
    """
    CU2 / CU3: Obtener un lienzo y su modelo UML persistido resolviendo el rol del participante.
    """
    user_id = current_user.id if current_user else None
    res = await service.obtener_lienzo(canvas_id, user_id=user_id)
    return _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name, res.role)


@router.post("/{canvas_id}/commands", response_model=CommandResponse)
async def execute_editor_command(
    canvas_id: str,
    command: EditorCommandRequest,
    service: CanvasServiceDep,
):
    """
    Ejecuta un comando del editor sobre el lienzo con control de versión optimista.
    """
    res, undo_payload = await service.ejecutar_comando(
        canvas_id=canvas_id,
        operation_id=command.operationId,
        expected_version=command.expectedVersion,
        cmd_type=command.type,
        payload=command.payload,
    )
    canvas_schema = _to_detail_schema(res.lienzo, res.version, res.owner_id, res.room_name)
    # "" nunca matchea un peer_id real (siempre uuid4().hex[:12]): este POST HTTP no
    # tiene un peer de WS propio que excluir, así que el broadcast llega a toda la sala.
    # El cliente descarta su propio eco comparando versión (ver EditorCommandService).
    await collaboration_room_registry.broadcast(
        canvas_id,
        "",
        {"type": "canvas_update", "canvas": canvas_schema.model_dump(mode="json")},
    )
    return CommandResponse(
        accepted=True,
        version=res.version,
        operationId=command.operationId,
        canvas=canvas_schema,
        undoPayload=undo_payload,
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

