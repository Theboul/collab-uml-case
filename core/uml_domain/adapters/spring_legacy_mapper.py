"""
Mapper específico para el generador legacy Spring Boot 3.5.5 (back_generator_uml).
"""

from typing import Any, Dict
from ..model import UmlDomainModel
from ..validation import SpringCompatibilityValidator
from .legacy_output_adapter import LegacyOutputAdapter, TransformationResult


class SpringLegacyMapper:
    """
    Transforma UML Domain Model V2 al formato UmlSchema esperado por Spring Boot.
    """

    @classmethod
    def to_spring_schema(cls, model: UmlDomainModel) -> TransformationResult:
        # 1. Transformación base hacia DTO legacy
        result = LegacyOutputAdapter.to_legacy_dto(model, target_generator="spring-boot-v1")

        # 2. Validación de compatibilidad Spring
        validator = SpringCompatibilityValidator()
        compat_res = validator.validate_compatibility(model)

        for issue in compat_res.issues:
            if issue.severity.value == "ERROR":
                result.report.unsupported_errors.append(f"[{issue.code}] {issue.message}")
            else:
                result.report.warnings.append(f"[{issue.code}] {issue.message}")

        result.report.is_compatible = len(result.report.unsupported_errors) == 0
        return result
