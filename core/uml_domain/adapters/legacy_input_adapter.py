"""
Adaptador de entrada: Transforma el formato Legacy v1 a UML Domain Model V2.
"""

from typing import Any, Dict, List, Optional
import uuid

from ..model import (
    UmlDomainModel,
    UmlClass,
    UmlAttribute,
    UmlOperation,
    UmlParameter,
    UmlAssociation,
    AssociationEnd,
    UmlGeneralization,
    UmlRealization,
    UmlDependency,
    UmlVisualLayout,
    ElementLayout,
    RelationshipLayout,
    VisibilityKind,
    AggregationKind,
    ParameterDirectionKind,
    MultiplicityRange,
)
from .multiplicity_parser import LegacyMultiplicityParser


class LegacyInputAdapter:
    """
    Ingesta payloads JSON del formato legacy (utilizados por Angular y persistidos en BD)
    y los mapea limpiamente a instancias puras de UML Domain Model V2.
    """

    @classmethod
    def to_v2_model(cls, legacy_json: Dict[str, Any], model_name: str = "ImportedModel") -> UmlDomainModel:
        raw_classes = legacy_json.get("classes", [])
        raw_relationships = legacy_json.get("relationships", [])

        classes: List[UmlClass] = []
        generalizations: List[UmlGeneralization] = []
        realizations: List[UmlRealization] = []
        dependencies: List[UmlDependency] = []
        associations: List[UmlAssociation] = []

        layout_nodes: Dict[str, ElementLayout] = {}
        layout_links: Dict[str, RelationshipLayout] = {}
        has_any_layout = False

        # 1. Transformar Clases
        for rc in raw_classes:
            cid = rc.get("id") or str(uuid.uuid4())
            cname = rc.get("name", "UnnamedClass")

            # Atributos
            attrs: List[UmlAttribute] = []
            raw_attrs = rc.get("attributes", [])
            if isinstance(raw_attrs, str):
                raw_attrs = cls._parse_attributes_from_string(raw_attrs)

            for ra in raw_attrs:
                aname = ra.get("name", "")
                atype = ra.get("type", "String")

                # Extraer visibilidad si viene como prefijo en el nombre (+, -, #, ~)
                visibility = VisibilityKind.PRIVATE
                if aname and aname[0] in ["+", "-", "#", "~"]:
                    visibility = VisibilityKind.from_symbol_or_str(aname[0])
                    aname = aname[1:].strip()

                attrs.append(
                    UmlAttribute(
                        id=str(uuid.uuid4()),
                        name=aname,
                        type=atype or "String",
                        visibility=visibility,
                        multiplicity=MultiplicityRange(1, 1),
                    )
                )

            # Métodos / Operaciones
            ops: List[UmlOperation] = []
            raw_methods = rc.get("methods", [])
            if isinstance(raw_methods, str):
                raw_methods = cls._parse_methods_from_string(raw_methods)

            for rm in raw_methods:
                mname = rm.get("name", "")
                mreturn = rm.get("returnType") or "void"
                mparams_raw = rm.get("parameters", "")

                visibility = VisibilityKind.PUBLIC
                if mname and mname[0] in ["+", "-", "#", "~"]:
                    visibility = VisibilityKind.from_symbol_or_str(mname[0])
                    mname = mname[1:].strip()

                # Parsear parámetros si vienen en formato texto "p1: Tipo, p2: Tipo"
                params: List[UmlParameter] = []
                if isinstance(mparams_raw, str) and mparams_raw.strip():
                    parts = [p.strip() for p in mparams_raw.split(",") if p.strip()]
                    for p in parts:
                        if ":" in p:
                            p_parts = p.split(":")
                            p_name = p_parts[0].strip()
                            p_type = p_parts[1].strip()
                        else:
                            # Formato estilo Java "int x"
                            tokens = p.split()
                            if len(tokens) >= 2:
                                p_type = tokens[0].strip()
                                p_name = tokens[1].strip()
                            else:
                                p_name = p.strip()
                                p_type = "Object"

                        params.append(
                            UmlParameter(
                                id=str(uuid.uuid4()),
                                name=p_name,
                                type=p_type,
                                direction=ParameterDirectionKind.IN,
                            )
                        )

                ops.append(
                    UmlOperation(
                        id=str(uuid.uuid4()),
                        name=mname,
                        return_type=mreturn,
                        visibility=visibility,
                        parameters=params,
                    )
                )

            classes.append(
                UmlClass(
                    id=cid,
                    name=cname,
                    visibility=VisibilityKind.PUBLIC,
                    attributes=attrs,
                    operations=ops,
                )
            )

            # Extraer geometría hacia UmlVisualLayout
            pos = rc.get("position")
            size = rc.get("size")
            if pos or size:
                has_any_layout = True
                layout_nodes[cid] = ElementLayout(
                    x=float(pos.get("x", 0.0)) if pos else 0.0,
                    y=float(pos.get("y", 0.0)) if pos else 0.0,
                    width=float(size.get("width", 180.0)) if size else 180.0,
                    height=float(size.get("height", 120.0)) if size else 120.0,
                )

        # 2. Transformar Relaciones
        for rr in raw_relationships:
            rid = rr.get("id") or str(uuid.uuid4())
            rtype = (rr.get("type") or "association").lower().strip()
            src_id = rr.get("sourceId", "")
            tgt_id = rr.get("targetId", "")
            labels = rr.get("labels") or []

            # Extraer waypoints para layout
            vertices = rr.get("vertices")
            if vertices is not None:
                has_any_layout = True
                layout_links[rid] = RelationshipLayout(vertices=vertices)

            # Mapeo según el tipo semántico
            if rtype == "generalization":
                generalizations.append(
                    UmlGeneralization(
                        id=rid,
                        specific_class_id=src_id,
                        general_class_id=tgt_id,
                    )
                )
            elif rtype == "realization":
                realizations.append(
                    UmlRealization(
                        id=rid,
                        client_class_id=src_id,
                        supplier_interface_id=tgt_id,
                    )
                )
            elif rtype == "dependency":
                dependencies.append(
                    UmlDependency(
                        id=rid,
                        client_class_id=src_id,
                        supplier_class_id=tgt_id,
                    )
                )
            else:
                # association, aggregation, composition
                # Parsear multiplicidades de labels
                raw_src_mult = labels[0] if len(labels) > 0 and labels[0] is not None else ""
                raw_tgt_mult = labels[1] if len(labels) > 1 and labels[1] is not None else ""

                src_mult = (
                    LegacyMultiplicityParser.parse(raw_src_mult)
                    if str(raw_src_mult).strip()
                    else MultiplicityRange(0, None)  # Fallback default legacy '*'
                )
                tgt_mult = (
                    LegacyMultiplicityParser.parse(raw_tgt_mult)
                    if str(raw_tgt_mult).strip()
                    else MultiplicityRange(1, 1)     # Fallback default legacy '1'
                )

                # Determinar aggregationKind
                agg_kind = AggregationKind.NONE
                if rtype == "aggregation":
                    agg_kind = AggregationKind.SHARED
                elif rtype == "composition":
                    agg_kind = AggregationKind.COMPOSITE

                source_end = AssociationEnd(
                    class_id=src_id,
                    multiplicity=src_mult,
                    aggregation_kind=AggregationKind.NONE,
                )
                target_end = AssociationEnd(
                    class_id=tgt_id,
                    multiplicity=tgt_mult,
                    aggregation_kind=agg_kind,
                )

                associations.append(
                    UmlAssociation(
                        id=rid,
                        member_ends=(source_end, target_end),
                    )
                )

        visual_layout = UmlVisualLayout(nodes=layout_nodes, links=layout_links) if has_any_layout else None

        return UmlDomainModel(
            schema_version="2.0.0",
            model_id=str(uuid.uuid4()),
            name=model_name,
            classes=classes,
            generalizations=generalizations,
            realizations=realizations,
            dependencies=dependencies,
            associations=associations,
            visual_layout=visual_layout,
        )

    @classmethod
    def _parse_attributes_from_string(cls, text: str) -> List[Dict[str, str]]:
        res = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                parts = line.split(":")
                res.append({"name": parts[0].strip(), "type": parts[1].strip()})
            else:
                res.append({"name": line, "type": "String"})
        return res

    @classmethod
    def _parse_methods_from_string(cls, text: str) -> List[Dict[str, str]]:
        res = []
        for line in text.split("\n"):
            line = line.strip()
            if not line:
                continue
            if "(" in line:
                parts = line.split("(")
                name = parts[0].strip()
                params = ""
                ret = "void"
                if len(parts) > 1 and ")" in parts[1]:
                    sub = parts[1].split(")")
                    params = sub[0].strip()
                    if len(sub) > 1 and ":" in sub[1]:
                        ret = sub[1].replace(":", "").strip()
                res.append({"name": name, "parameters": params, "returnType": ret})
            else:
                res.append({"name": line, "parameters": "", "returnType": "void"})
        return res
