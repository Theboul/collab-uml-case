"""
Rutas API v2 para el módulo de modelado UML (CU1 - CU4).
"""
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from backend_case.app.application.mappers import DomainToPydanticMapper
from backend_case.app.modeling.application.canvas_service import CanvasService
from backend_case.app.schemas.uml import UmlModelSchema
from backend_case.app.shared.deps import get_canvas_service
from core.uml_domain.model import Lienzo

router = APIRouter(prefix="/canvases", tags=["modeling"])

CanvasServiceDep = Annotated[CanvasService, Depends(get_canvas_service)]


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


class CanvasSummarySchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    version: int
    created_at: str | None = None
    updated_at: str | None = None


class CanvasDetailSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    version: int
    visualLayout: dict[str, Any] = Field(default_factory=dict)
    model: UmlModelSchema


def _to_detail_schema(lienzo: Lienzo, version: int) -> CanvasDetailSchema:
    model_schema = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo)
    return CanvasDetailSchema(
        id=lienzo.id,
        name=lienzo.modelo.name,
        description=lienzo.modelo.description,
        version=version,
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
):
    """
    CU1: Crear un nuevo lienzo UML persistido.
    """
    lienzo, version, _ = await service.crear_lienzo(
        nombre=payload.name,
        descripcion=payload.description,
    )
    return _to_detail_schema(lienzo, version)


@router.get("/{canvas_id}", response_model=CanvasDetailSchema)
async def get_canvas(
    canvas_id: str,
    service: CanvasServiceDep,
):
    """
    CU2 / CU3: Obtener un lienzo y su modelo UML persistido.
    """
    lienzo, version = await service.obtener_lienzo(canvas_id)
    return _to_detail_schema(lienzo, version)


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
