"""
Pruebas unitarias para las entidades del UML Domain Model V2.
"""

import pytest
from core.uml_domain.model import (
    UmlDomainModel,
    UmlClass,
    UmlInterface,
    UmlEnumeration,
    UmlDataType,
    UmlAttribute,
    UmlOperation,
    UmlParameter,
    UmlAssociation,
    AssociationEnd,
    UmlGeneralization,
    UmlRealization,
    UmlDependency,
    MultiplicityRange,
    VisibilityKind,
    AggregationKind,
    ParameterDirectionKind,
    UmlVisualLayout,
    ElementLayout,
    RelationshipLayout,
    ViewportLayout,
)


def test_multiplicity_range_validations():
    m1 = MultiplicityRange(lower=1, upper=1)
    assert not m1.is_many
    assert not m1.is_optional
    assert m1.to_uml_str() == "1"

    m_many = MultiplicityRange(lower=0, upper=None)
    assert m_many.is_many
    assert m_many.is_optional
    assert m_many.to_uml_str() == "*"

    m_range = MultiplicityRange(lower=2, upper=5)
    assert m_range.is_many
    assert not m_range.is_optional
    assert m_range.to_uml_str() == "2..5"

    # Cotas inválidas deben arrojar ValueError
    with pytest.raises(ValueError, match="no puede ser negativa"):
        MultiplicityRange(lower=-1, upper=1)

    with pytest.raises(ValueError, match="no puede ser menor"):
        MultiplicityRange(lower=5, upper=2)


def test_classifiers_creation():
    cls_elem = UmlClass(
        id="c1",
        name="Cliente",
        visibility=VisibilityKind.PUBLIC,
        is_abstract=False,
        is_interface=False,
    )
    assert cls_elem.name == "Cliente"
    assert cls_elem.visibility == VisibilityKind.PUBLIC

    interface_elem = UmlInterface(id="i1", name="IRepositorio")
    assert interface_elem.name == "IRepositorio"

    enum_elem = UmlEnumeration(id="e1", name="EstadoPedido", literals=["PENDIENTE", "ENVIADO", "ENTREGADO"])
    assert len(enum_elem.literals) == 3

    dtype_elem = UmlDataType(id="d1", name="Direccion")
    assert dtype_elem.name == "Direccion"


def test_attributes_and_operations():
    attr = UmlAttribute(
        id="a1",
        name="email",
        type="String",
        visibility=VisibilityKind.PRIVATE,
        is_read_only=False,
    )
    assert attr.name == "email"
    assert attr.visibility == VisibilityKind.PRIVATE

    param = UmlParameter(id="p1", name="porcentaje", type="Double", direction=ParameterDirectionKind.IN)
    op = UmlOperation(
        id="op1",
        name="calcularDescuento",
        return_type="Double",
        visibility=VisibilityKind.PUBLIC,
        parameters=[param],
    )
    assert op.name == "calcularDescuento"
    assert len(op.parameters) == 1
    assert op.parameters[0].name == "porcentaje"


def test_relationships_semantics():
    # Asociación con aggregationKind en AssociationEnd
    end_cliente = AssociationEnd(class_id="c1", multiplicity=MultiplicityRange(1, 1), aggregation_kind=AggregationKind.NONE)
    end_pedido = AssociationEnd(class_id="c2", multiplicity=MultiplicityRange(0, None), aggregation_kind=AggregationKind.NONE)
    assoc = UmlAssociation(id="r1", name="realiza", member_ends=(end_cliente, end_pedido))
    assert assoc.name == "realiza"
    assert assoc.member_ends[0].class_id == "c1"
    assert assoc.member_ends[1].multiplicity.is_many

    # Generalización (semántica de herencia directa sin multiplicidades)
    gen = UmlGeneralization(id="g1", specific_class_id="sub", general_class_id="super")
    assert gen.specific_class_id == "sub"
    assert gen.general_class_id == "super"

    # Realización (cliente -> interfaz)
    real = UmlRealization(id="re1", client_class_id="c1", supplier_interface_id="i1")
    assert real.client_class_id == "c1"

    # Dependencia (cliente -> proveedor)
    dep = UmlDependency(id="d1", client_class_id="c1", supplier_class_id="c3")
    assert dep.supplier_class_id == "c3"


def test_layout_separation_and_optionality():
    # Modelo sin layout funciona 100% de forma autónoma
    model_headless = UmlDomainModel(
        schema_version="2.0.0",
        model_id="m1",
        name="HeadlessModel",
        classes=[UmlClass(id="c1", name="Usuario")],
        visual_layout=None,
    )
    assert model_headless.visual_layout is None
    assert len(model_headless.classes) == 1

    # Modelo con layout opcional
    layout = UmlVisualLayout(
        viewport=ViewportLayout(zoom=1.5, pan_x=10, pan_y=20),
        nodes={"c1": ElementLayout(x=100.0, y=150.0, width=200.0, height=140.0)},
        links={"r1": RelationshipLayout(vertices=[{"x": 150.0, "y": 200.0}])},
    )
    model_with_layout = UmlDomainModel(
        schema_version="2.0.0",
        model_id="m2",
        name="VisualModel",
        classes=[UmlClass(id="c1", name="Usuario")],
        visual_layout=layout,
    )
    assert model_with_layout.visual_layout is not None
    assert model_with_layout.visual_layout.nodes["c1"].x == 100.0
