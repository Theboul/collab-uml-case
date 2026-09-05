"""
Módulo de adaptadores legacy y transformación bidireccional V1 <-> V2.
"""

from .multiplicity_parser import LegacyMultiplicityParser
from .legacy_input_adapter import LegacyInputAdapter
from .legacy_output_adapter import (
    LegacyOutputAdapter,
    TransformationReport,
    TransformationResult,
)
from .spring_legacy_mapper import SpringLegacyMapper
from .flutter_legacy_mapper import FlutterLegacyMapper

__all__ = [
    "LegacyMultiplicityParser",
    "LegacyInputAdapter",
    "LegacyOutputAdapter",
    "TransformationReport",
    "TransformationResult",
    "SpringLegacyMapper",
    "FlutterLegacyMapper",
]
