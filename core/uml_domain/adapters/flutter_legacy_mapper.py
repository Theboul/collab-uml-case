"""
Mapper específico para el generador legacy Flutter CRUD (back_generador_bd).
"""

from typing import Any, Dict
from ..model import UmlDomainModel
from ..validation import FlutterCompatibilityValidator
from .legacy_output_adapter import LegacyOutputAdapter, TransformationResult


class FlutterLegacyMapper:
    """
    Transforma UML Domain Model V2 al formato JSON esperado por FlutterCRUDGenerator.
    """

    @classmethod
    def to_flutter_json(cls, model: UmlDomainModel) -> TransformationResult:
        # 1. Transformación base hacia DTO legacy
        result = LegacyOutputAdapter.to_legacy_dto(model, target_generator="flutter-crud-v1")

        # 2. Validación de compatibilidad Flutter
        validator = FlutterCompatibilityValidator()
        compat_res = validator.validate_compatibility(model)

        for issue in compat_res.issues:
            if issue.severity.value == "ERROR":
                result.report.unsupported_errors.append(f"[{issue.code}] {issue.message}")
            else:
                result.report.warnings.append(f"[{issue.code}] {issue.message}")

        result.report.is_compatible = len(result.report.unsupported_errors) == 0
        return result
