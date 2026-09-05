"""
Servicios de la capa de aplicación.
Orquestan las operaciones de negocio invocando al motor de dominio puro
sin acoplar lógica dentro del framework FastAPI.
"""

from core.uml_domain.validation import (
    FlutterCompatibilityValidator,
    SpringCompatibilityValidator,
    UMLValidator,
    ValidationResult,
)

from ..schemas.uml import (
    UmlModelSchema,
    ValidationIssueSchema,
    ValidationResponseSchema,
)
from .mappers import PydanticToDomainMapper


class UmlApplicationService:
    """
    Servicio de aplicación para validación y compatibilidad de modelos UML.
    """

    def __init__(self):
        self.uml_validator = UMLValidator()
        self.spring_validator = SpringCompatibilityValidator()
        self.flutter_validator = FlutterCompatibilityValidator()

    def validate_uml_model(self, model_dto: UmlModelSchema) -> ValidationResponseSchema:
        domain_model = PydanticToDomainMapper.to_domain_model(model_dto)
        val_result = self.uml_validator.validate(domain_model)
        return self._build_response(val_result)

    def check_spring_compatibility(self, model_dto: UmlModelSchema) -> ValidationResponseSchema:
        domain_model = PydanticToDomainMapper.to_domain_model(model_dto)
        # 1. Comprobar validez semántica básica
        val_result = self.uml_validator.validate(domain_model)
        # 2. Comprobar compatibilidad con el perfil Spring Boot
        spring_res = self.spring_validator.validate_compatibility(domain_model)
        # Combinar issues
        combined_issues = val_result.issues + spring_res.issues
        combined_result = ValidationResult(issues=combined_issues)
        return self._build_response(combined_result)

    def check_flutter_compatibility(self, model_dto: UmlModelSchema) -> ValidationResponseSchema:
        domain_model = PydanticToDomainMapper.to_domain_model(model_dto)
        # 1. Comprobar validez semántica básica
        val_result = self.uml_validator.validate(domain_model)
        # 2. Comprobar compatibilidad con el perfil Flutter CRUD
        flutter_res = self.flutter_validator.validate_compatibility(domain_model)
        combined_issues = val_result.issues + flutter_res.issues
        combined_result = ValidationResult(issues=combined_issues)
        return self._build_response(combined_result)

    def _build_response(self, result: ValidationResult) -> ValidationResponseSchema:
        errors = [
            ValidationIssueSchema(
                code=i.code,
                message=i.message,
                severity="ERROR",
                elementId=i.element_id,
            )
            for i in result.errors
        ]
        warnings = [
            ValidationIssueSchema(
                code=i.code,
                message=i.message,
                severity="WARNING",
                elementId=i.element_id,
            )
            for i in result.warnings
        ]
        return ValidationResponseSchema(
            valid=result.is_valid,
            errors=errors,
            warnings=warnings,
        )
