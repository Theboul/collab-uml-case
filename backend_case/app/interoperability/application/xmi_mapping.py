"""
Mapeo puro XMI 1.1 / UML 1.3 (dialecto real de Enterprise Architect) <-> core.uml_domain (CU8).

Confirmado línea por línea contra un archivo real exportado por EA 2.5
(docs/spec/ejemplo de diagrama de clases ea.xml): namespace UML="omg.org/UML1.3",
atributos/operaciones anidados en Classifier.feature, tipos resueltos por xmi.idref
contra una tabla de UML:DataType, retorno de operación como Parameter kind="return",
extremos de asociación por atributo type="<xmi.id de la clase>", y layout en un
bloque <UML:Diagram> separado del modelo semántico.

Sin dependencias de FastAPI/Pydantic — solo xml.etree.ElementTree y las dataclasses
puras de core.uml_domain.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass

from core.uml_domain.adapters.multiplicity_parser import LegacyMultiplicityParser
from core.uml_domain.model import (
    AggregationKind,
    AssociationEnd,
    Lienzo,
    ParameterDirectionKind,
    UmlAssociation,
    UmlAttribute,
    UmlClass,
    UmlDomainModel,
    UmlOperation,
    UmlParameter,
    VisibilityKind,
)

UML_NS = "omg.org/UML1.3"
ET.register_namespace("UML", UML_NS)

_KIND_TO_DIRECTION = {
    "in": ParameterDirectionKind.IN,
    "out": ParameterDirectionKind.OUT,
    "inout": ParameterDirectionKind.INOUT,
}


class XmiParseError(ValueError):
    """XML malformado o sin la estructura mínima <UML:Model> esperada por este dialecto."""


@dataclass
class XmiImportWarning:
    code: str
    message: str
    element_id: str | None = None


def _q(tag: str) -> str:
    """Nombre de tag calificado con el namespace UML1.3 (xmlns:UML="omg.org/UML1.3")."""
    return f"{{{UML_NS}}}{tag}"


def _iter_namespace_children(namespace_element: ET.Element) -> Iterator[ET.Element]:
    """
    Recorre recursivamente un UML:Namespace.ownedElement, entrando en cada UML:Package
    anidado (puede haber varios niveles), devolviendo cada UML:Class/Association/
    Generalization encontrado a cualquier profundidad. Ignora clases sintéticas de EA
    (isRoot="true", ej. "EARootClass") que no son parte del diagrama del usuario.
    """
    for child in namespace_element:
        if child.tag == _q("Package"):
            inner_ns = child.find(_q("Namespace.ownedElement"))
            if inner_ns is not None:
                yield from _iter_namespace_children(inner_ns)
        elif child.tag == _q("Class"):
            if child.get("isRoot") == "true":
                continue
            yield child
        elif child.tag in (_q("Association"), _q("Generalization")):
            yield child


def _build_datatype_table(model_element: ET.Element) -> dict[str, str]:
    """xmi.id -> name, para resolver StructuralFeature.type/Parameter.type por xmi.idref."""
    table: dict[str, str] = {}
    for dt in model_element.iter(_q("DataType")):
        xid = dt.get("xmi.id")
        if xid:
            table[xid] = dt.get("name", "String")
    return table


def _resolve_type_idref(type_container: ET.Element | None, datatype_table: dict[str, str]) -> str:
    if type_container is None:
        return "String"
    classifier_ref = type_container.find(_q("Classifier"))
    if classifier_ref is None:
        return "String"
    idref = classifier_ref.get("xmi.idref")
    return datatype_table.get(idref, "String") if idref else "String"


def _parse_class(class_element: ET.Element, datatype_table: dict[str, str]) -> UmlClass:
    attributes: list[UmlAttribute] = []
    operations: list[UmlOperation] = []

    feature_container = class_element.find(_q("Classifier.feature"))
    if feature_container is not None:
        for attr_el in feature_container.findall(_q("Attribute")):
            type_container = attr_el.find(_q("StructuralFeature.type"))
            attributes.append(
                UmlAttribute(
                    name=attr_el.get("name", ""),
                    type=_resolve_type_idref(type_container, datatype_table),
                    visibility=VisibilityKind.from_symbol_or_str(attr_el.get("visibility")),
                )
            )

        for op_el in feature_container.findall(_q("Operation")):
            params: list[UmlParameter] = []
            return_type = "void"
            param_container = op_el.find(_q("BehavioralFeature.parameter"))
            if param_container is not None:
                for p_el in param_container.findall(_q("Parameter")):
                    p_type_container = p_el.find(_q("Parameter.type"))
                    resolved_type = _resolve_type_idref(p_type_container, datatype_table)
                    if p_el.get("kind") == "return":
                        return_type = resolved_type
                    else:
                        params.append(
                            UmlParameter(
                                name=p_el.get("name", ""),
                                type=resolved_type,
                                direction=_KIND_TO_DIRECTION.get(
                                    p_el.get("kind", "in"), ParameterDirectionKind.IN
                                ),
                            )
                        )

            operations.append(
                UmlOperation(
                    name=op_el.get("name", ""),
                    return_type=return_type,
                    visibility=VisibilityKind.from_symbol_or_str(op_el.get("visibility")),
                    parameters=params,
                )
            )

    return UmlClass(
        id=class_element.get("xmi.id", ""),
        name=class_element.get("name", ""),
        visibility=VisibilityKind.from_symbol_or_str(class_element.get("visibility")),
        is_abstract=class_element.get("isAbstract") == "true",
        attributes=attributes,
        operations=operations,
    )


_EA_TO_DOMAIN_AGGREGATION = {
    "none": AggregationKind.NONE,
    "aggregate": AggregationKind.SHARED,
    "shared": AggregationKind.SHARED,
    "composite": AggregationKind.COMPOSITE,
}

_DOMAIN_TO_EA_AGGREGATION = {
    AggregationKind.NONE: "none",
    AggregationKind.SHARED: "aggregate",
    AggregationKind.COMPOSITE: "composite",
}


def _parse_association(assoc_element: ET.Element) -> UmlAssociation | None:
    connection = assoc_element.find(_q("Association.connection"))
    if connection is None:
        return None
    ends = connection.findall(_q("AssociationEnd"))
    if len(ends) != 2:
        return None

    def _to_domain_end(end_el: ET.Element) -> AssociationEnd:
        raw_agg = (end_el.get("aggregation") or "none").lower()
        agg_kind = _EA_TO_DOMAIN_AGGREGATION.get(raw_agg, AggregationKind.NONE)
        return AssociationEnd(
            class_id=end_el.get("type", ""),
            role_name=end_el.get("name") or None,
            aggregation_kind=agg_kind,
            multiplicity=LegacyMultiplicityParser.parse(end_el.get("multiplicity", "1")),
        )

    return UmlAssociation(
        id=assoc_element.get("xmi.id", ""),
        name=assoc_element.get("name") or None,
        member_ends=(_to_domain_end(ends[0]), _to_domain_end(ends[1])),
    )


def _parse_class_positions(root: ET.Element) -> dict[str, dict[str, float]]:
    """
    Lee UML:Diagram > UML:Diagram.element > UML:DiagramElement[geometry, subject] y
    arma un dict class_id -> {x, y, width, height} en el mismo formato que ya usa
    Lienzo.visual_layout["nodes"] en el resto del backend (dict plano, no dataclass).
    """
    positions: dict[str, dict[str, float]] = {}
    for diagram_el in root.iter(_q("DiagramElement")):
        subject = diagram_el.get("subject")
        geometry = diagram_el.get("geometry", "")
        if not subject or not geometry:
            continue
        parts = dict(item.split("=", 1) for item in geometry.split(";") if "=" in item)
        if "Left" not in parts or "Top" not in parts:
            continue
        try:
            left, top = float(parts["Left"]), float(parts["Top"])
            right = float(parts.get("Right", left + 180))
            bottom = float(parts.get("Bottom", top + 120))
        except ValueError:
            continue
        positions[subject] = {"x": left, "y": top, "width": right - left, "height": bottom - top}
    return positions


def parse_xmi_document(
    xmi_bytes: bytes,
) -> tuple[UmlDomainModel, dict[str, dict[str, float]], list[XmiImportWarning]]:
    """
    Punto de entrada del import: bytes crudos del archivo (respeta el encoding
    declarado en el prolog, ej. windows-1252 en EA) -> (UmlDomainModel, posiciones
    por class_id, advertencias de elementos no soportados/no verificados).
    """
    try:
        root = ET.fromstring(xmi_bytes)
    except ET.ParseError as exc:
        raise XmiParseError(f"XML malformado: {exc}") from exc

    model_element = root.find(f".//{_q('Model')}")
    if model_element is None:
        raise XmiParseError("No se encontró <UML:Model> en el documento XMI.")

    datatype_table = _build_datatype_table(model_element)
    top_namespace = model_element.find(_q("Namespace.ownedElement"))

    classes: list[UmlClass] = []
    associations: list[UmlAssociation] = []
    warnings: list[XmiImportWarning] = []

    if top_namespace is not None:
        for element in _iter_namespace_children(top_namespace):
            if element.tag == _q("Class"):
                classes.append(_parse_class(element, datatype_table))
            elif element.tag == _q("Association"):
                assoc = _parse_association(element)
                if assoc is not None:
                    associations.append(assoc)
                else:
                    warnings.append(
                        XmiImportWarning(
                            code="XMI_UNSUPPORTED_ASSOCIATION_SHAPE",
                            message=(
                                f"Asociación '{element.get('name')}' con forma no reconocida, "
                                "omitida."
                            ),
                            element_id=element.get("xmi.id"),
                        )
                    )
            elif element.tag == _q("Generalization"):
                warnings.append(
                    XmiImportWarning(
                        code="XMI_GENERALIZATION_NOT_VERIFIED",
                        message=(
                            "Generalización encontrada pero el import de herencia en este "
                            "dialecto no está verificado contra un archivo real de EA todavía "
                            "— omitida. Ver Sección 9 de la ficha CU8."
                        ),
                        element_id=element.get("xmi.id"),
                    )
                )

    model = UmlDomainModel(
        name=model_element.get("name") or "Modelo Importado",
        classes=classes,
        associations=associations,
    )
    positions = _parse_class_positions(root)
    return model, positions, warnings


def build_xmi_document(lienzo: Lienzo) -> bytes:
    """
    Genera un documento XMI 1.1/UML 1.3 bien formado a partir de un lienzo persistido.
    Encoding de salida: UTF-8 (decisión explícita — EA acepta cualquier encoding
    declarado en el prolog; no hace falta replicar windows-1252 de la fuente).
    No reconstruye la geometría fina de las aristas (formato interno $LLB=... de EA),
    solo la posición x/y/ancho/alto de cada clase.
    """
    model = lienzo.modelo

    xmi_root = ET.Element("XMI", {"xmi.version": "1.1"})
    header = ET.SubElement(xmi_root, "XMI.header")
    documentation = ET.SubElement(header, "XMI.documentation")
    ET.SubElement(documentation, "XMI.exporter").text = "SchemaCraft"
    ET.SubElement(documentation, "XMI.exporterVersion").text = "1.0"

    content = ET.SubElement(xmi_root, "XMI.content")
    model_el = ET.SubElement(content, _q("Model"), {"name": model.name, "xmi.id": model.model_id})
    top_ns = ET.SubElement(model_el, _q("Namespace.ownedElement"))

    datatype_ids: dict[str, str] = {}

    def _datatype_idref(type_name: str) -> str:
        if type_name not in datatype_ids:
            datatype_ids[type_name] = f"dt_{len(datatype_ids)}"
        return datatype_ids[type_name]

    def _add_type_ref(parent: ET.Element, container_tag: str, type_name: str) -> None:
        container = ET.SubElement(parent, _q(container_tag))
        ET.SubElement(container, _q("Classifier"), {"xmi.idref": _datatype_idref(type_name)})

    for c in model.classes:
        class_el = ET.SubElement(
            top_ns,
            _q("Class"),
            {
                "xmi.id": c.id,
                "name": c.name,
                "visibility": c.visibility.value,
                "isAbstract": str(c.is_abstract).lower(),
            },
        )
        if c.attributes or c.operations:
            feature_el = ET.SubElement(class_el, _q("Classifier.feature"))
            for a in c.attributes:
                attr_el = ET.SubElement(
                    feature_el, _q("Attribute"), {"name": a.name, "visibility": a.visibility.value}
                )
                _add_type_ref(attr_el, "StructuralFeature.type", a.type)

            for op in c.operations:
                op_attrs = {"name": op.name, "visibility": op.visibility.value}
                op_el = ET.SubElement(feature_el, _q("Operation"), op_attrs)
                params_el = ET.SubElement(op_el, _q("BehavioralFeature.parameter"))

                return_param = ET.SubElement(params_el, _q("Parameter"), {"kind": "return"})
                _add_type_ref(return_param, "Parameter.type", op.return_type)

                for p in op.parameters:
                    p_el = ET.SubElement(
                        params_el, _q("Parameter"), {"name": p.name, "kind": p.direction.value}
                    )
                    _add_type_ref(p_el, "Parameter.type", p.type)

    for assoc in model.associations:
        assoc_attrs = {"xmi.id": assoc.id, "name": assoc.name or ""}
        assoc_el = ET.SubElement(top_ns, _q("Association"), assoc_attrs)
        connection_el = ET.SubElement(assoc_el, _q("Association.connection"))
        for end in assoc.member_ends:
            ET.SubElement(
                connection_el,
                _q("AssociationEnd"),
                {
                    "type": end.class_id,
                    "name": end.role_name or "",
                    "aggregation": _DOMAIN_TO_EA_AGGREGATION.get(end.aggregation_kind, "none"),
                    "multiplicity": end.multiplicity.to_uml_str(),
                    "isNavigable": str(end.is_navigable).lower(),
                },
            )

    for g in model.generalizations:
        ET.SubElement(
            top_ns,
            _q("Generalization"),
            {"xmi.id": g.id, "subtype": g.specific_class_id, "supertype": g.general_class_id},
        )

    for type_name, xid in datatype_ids.items():
        ET.SubElement(top_ns, _q("DataType"), {"xmi.id": xid, "name": type_name})

    nodes = lienzo.visual_layout.get("nodes", {}) if isinstance(lienzo.visual_layout, dict) else {}
    if nodes:
        diagram_el = ET.SubElement(
            content, _q("Diagram"), {"name": model.name, "diagramType": "ClassDiagram"}
        )
        elements_el = ET.SubElement(diagram_el, _q("Diagram.element"))
        for class_id, layout in nodes.items():
            x, y = float(layout.get("x", 0)), float(layout.get("y", 0))
            width = float(layout.get("width", 180))
            height = float(layout.get("height", 120))
            right, bottom = int(x + width), int(y + height)
            geometry = f"Left={int(x)};Top={int(y)};Right={right};Bottom={bottom};"
            ET.SubElement(
                elements_el, _q("DiagramElement"), {"geometry": geometry, "subject": class_id}
            )

    result: bytes = ET.tostring(xmi_root, encoding="utf-8", xml_declaration=True)
    return result
