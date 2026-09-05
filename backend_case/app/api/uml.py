"""
Endpoints de validación y compatibilidad de diagramas de clases UML v2.
"""

from fastapi import APIRouter, Depends

from ..application.services import UmlApplicationService
from ..schemas.uml import UmlModelSchema, ValidationResponseSchema

router = APIRouter(prefix="/api/v2/uml", tags=["UML"])


def get_uml_service() -> UmlApplicationService:
    return UmlApplicationService()


@router.post("/validate", response_model=ValidationResponseSchema, summary="Valida semánticamente un modelo UML 2.5")
def validate_uml(
    model: UmlModelSchema,
    service: UmlApplicationService = Depends(get_uml_service),
) -> ValidationResponseSchema:
    return service.validate_uml_model(model)


@router.post("/compatibility/spring", response_model=ValidationResponseSchema, summary="Evalúa compatibilidad con Spring Boot v1")
def check_spring_compatibility(
    model: UmlModelSchema,
    service: UmlApplicationService = Depends(get_uml_service),
) -> ValidationResponseSchema:
    return service.check_spring_compatibility(model)


@router.post("/compatibility/flutter", response_model=ValidationResponseSchema, summary="Evalúa compatibilidad con Flutter CRUD v1")
def check_flutter_compatibility(
    model: UmlModelSchema,
    service: UmlApplicationService = Depends(get_uml_service),
) -> ValidationResponseSchema:
    return service.check_flutter_compatibility(model)
