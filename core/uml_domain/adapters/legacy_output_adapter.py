"""
Adaptador de salida: Transforma UML Domain Model V2 al formato Legacy compatible
con auditoría de no pérdida de datos (No Silent Loss).
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..model import (
    UmlDomainModel,
    AggregationKind,
)


@dataclass
class TransformationReport:
    target_generator: str
    is_compatible: bool = True
    warnings: List[str] = field(default_factory=list)
    degradations: List[str] = field(default_factory=list)
    unsupported_errors: List[str] = field(default_factory=list)


@dataclass
class TransformationResult:
    payload: Dict[str, Any]
    report: TransformationReport


class LegacyOutputAdapter:
    """
    Exportador canónico desde UML Domain Model V2 hacia contratos legacy.
    Garantiza que ninguna característica V2 no soportada por generadores
    antiguos se descarte de forma silenciosa.
    """

    @classmethod
    def to_legacy_dto(cls, model: UmlDomainModel, target_generator: str = "generic-legacy") -> TransformationResult:
        report = TransformationReport(target_generator=target_generator)

        # 1. Auditoría de características V2 no soportadas en legacy
        if model.interfaces:
            msg = f"El generador '{target_generator}' no soporta interfaces formales ({len(model.interfaces)} omitidas)."
            report.degradations.append(msg)

        if model.realizations:
            msg = f"El generador '{target_generator}' no soporta relaciones de realización ({len(model.realizations)} omitidas)."
            report.degradations.append(msg)

        if model.dependencies:
            msg = f"El generador '{target_generator}' no soporta relaciones de dependencia ({len(model.dependencies)} omitidas)."
            report.warnings.append(msg)

        # 2. Mapear Clases
        classes_payload: List[Dict[str, Any]] = []
        for c in model.classes:
            attrs_payload = []
            for a in c.attributes:
                attrs_payload.append({
                    "name": a.name,
                    "type": a.type
                })

            methods_payload = []
            for m in c.operations:
                params_str = ", ".join(f"{p.name}: {p.type}" for p in m.parameters)
                methods_payload.append({
                    "name": m.name,
                    "parameters": params_str,
                    "returnType": m.return_type
                })

            class_dict: Dict[str, Any] = {
                "id": c.id,
                "name": c.name,
                "attributes": attrs_payload,
                "methods": methods_payload
            }

            # Si el modelo posee layout visual, proyectar posición y tamaño
            if model.visual_layout and c.id in model.visual_layout.nodes:
                node_layout = model.visual_layout.nodes[c.id]
                class_dict["position"] = {"x": node_layout.x, "y": node_layout.y}
                class_dict["size"] = {"width": node_layout.width, "height": node_layout.height}

            classes_payload.append(class_dict)

        # 3. Mapear Relaciones
        relationships_payload: List[Dict[str, Any]] = []

        # A. Generalizaciones
        for gen in model.generalizations:
            rel_dict: Dict[str, Any] = {
                "id": gen.id,
                "type": "generalization",
                "sourceId": gen.specific_class_id,
                "targetId": gen.general_class_id,
                "labels": []
            }
            if model.visual_layout and gen.id in model.visual_layout.links:
                rel_dict["vertices"] = model.visual_layout.links[gen.id].vertices
            relationships_payload.append(rel_dict)

        # B. Asociaciones (incluyen agregación y composición según aggregationKind)
        for assoc in model.associations:
            source_end, target_end = assoc.member_ends

            rtype = "association"
            if target_end.aggregation_kind == AggregationKind.COMPOSITE or source_end.aggregation_kind == AggregationKind.COMPOSITE:
                rtype = "composition"
            elif target_end.aggregation_kind == AggregationKind.SHARED or source_end.aggregation_kind == AggregationKind.SHARED:
                rtype = "aggregation"

            src_label = source_end.multiplicity.to_uml_str()
            tgt_label = target_end.multiplicity.to_uml_str()

            rel_dict = {
                "id": assoc.id,
                "type": rtype,
                "sourceId": source_end.class_id,
                "targetId": target_end.class_id,
                "labels": [src_label, tgt_label]
            }
            if model.visual_layout and assoc.id in model.visual_layout.links:
                rel_dict["vertices"] = model.visual_layout.links[assoc.id].vertices
            relationships_payload.append(rel_dict)

        # Determinar compatibilidad
        report.is_compatible = len(report.unsupported_errors) == 0

        payload = {
            "classes": classes_payload,
            "relationships": relationships_payload
        }

        return TransformationResult(payload=payload, report=report)
