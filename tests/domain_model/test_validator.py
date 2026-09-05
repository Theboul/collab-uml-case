"""
Pruebas del motor de validación semántica UML 2.5 y validadores de compatibilidad.
"""

import pytest
from core.uml_domain.model import (
    UmlDomainModel,
    UmlClass,
    UmlInterface,
    UmlAttribute,
    UmlOperation,
    UmlParameter,
    UmlAssociation,
    AssociationEnd,
    UmlGeneralization,
    UmlRealization,
    MultiplicityRange,
    AggregationKind,
)
from core.uml_domain.validation import (
    UMLValidator,
    SpringCompatibilityValidator,
    ValidationSeverity,
)


@pytest.fixture
def validator():
    return UMLValidator()


def test_valid_model(validator):
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="ValidModel",
        classes=[
            UmlClass(id="c1", name="Cliente", attributes=[UmlAttribute(id="a1", name="id", type="Long")]),
            UmlClass(id="c2", name="Pedido", attributes=[UmlAttribute(id="a2", name="total", type="Double")]),
        ],
        associations=[
            UmlAssociation(
                id="r1",
                member_ends=(
                    AssociationEnd(class_id="c1", multiplicity=MultiplicityRange(1, 1)),
                    AssociationEnd(class_id="c2", multiplicity=MultiplicityRange(0, None)),
                ),
            )
        ],
    )
    res = validator.validate(model)
    assert res.is_valid
    assert len(res.errors) == 0


def test_duplicate_ids(validator):
    # Usar mismo ID en dos clases
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="DupIdModel",
        classes=[
            UmlClass(id="same-id", name="Cliente"),
            UmlClass(id="same-id", name="Pedido"),
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-02" for i in res.errors)


def test_missing_reference(validator):
    # Asociación apunta a clase inexistente
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="MissingRefModel",
        classes=[UmlClass(id="c1", name="Cliente")],
        associations=[
            UmlAssociation(
                id="r1",
                member_ends=(
                    AssociationEnd(class_id="c1", multiplicity=MultiplicityRange(1, 1)),
                    AssociationEnd(class_id="non-existent-id", multiplicity=MultiplicityRange(1, 1)),
                ),
            )
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-11" for i in res.errors)


def test_circular_generalization(validator):
    # A -> B -> C -> A (Ciclo en herencia)
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="CyclicModel",
        classes=[
            UmlClass(id="c_a", name="A"),
            UmlClass(id="c_b", name="B"),
            UmlClass(id="c_c", name="C"),
        ],
        generalizations=[
            UmlGeneralization(id="g1", specific_class_id="c_a", general_class_id="c_b"),
            UmlGeneralization(id="g2", specific_class_id="c_b", general_class_id="c_c"),
            UmlGeneralization(id="g3", specific_class_id="c_c", general_class_id="c_a"),
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-07" for i in res.errors)


def test_realization_pointing_to_non_interface(validator):
    # Realización apunta a una clase concreta en vez de interfaz
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="RealizationModel",
        classes=[
            UmlClass(id="c_client", name="ClienteService", is_interface=False),
            UmlClass(id="c_supplier", name="ProveedorService", is_interface=False),
        ],
        realizations=[
            UmlRealization(id="re1", client_class_id="c_client", supplier_interface_id="c_supplier"),
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-09" for i in res.errors)


def test_invalid_composition_multiplicity(validator):
    # En composición, el todo no puede tener multiplicidad > 1
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="CompModel",
        classes=[
            UmlClass(id="c1", name="Edificio"),
            UmlClass(id="c2", name="Habitacion"),
        ],
        associations=[
            UmlAssociation(
                id="r1",
                member_ends=(
                    AssociationEnd(
                        class_id="c1",
                        multiplicity=MultiplicityRange(2, 5),  # INVÁLIDO: compuesto con upper > 1
                        aggregation_kind=AggregationKind.COMPOSITE,
                    ),
                    AssociationEnd(
                        class_id="c2",
                        multiplicity=MultiplicityRange(1, None),
                        aggregation_kind=AggregationKind.NONE,
                    ),
                ),
            )
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-12" for i in res.errors)


def test_duplicate_attributes_within_class(validator):
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="DupAttrModel",
        classes=[
            UmlClass(
                id="c1",
                name="Persona",
                attributes=[
                    UmlAttribute(id="a1", name="edad", type="Integer"),
                    UmlAttribute(id="a2", name="edad", type="Integer"),
                ],
            )
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-04" for i in res.errors)


def test_duplicate_method_signatures(validator):
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="DupMethodModel",
        classes=[
            UmlClass(
                id="c1",
                name="Calculadora",
                operations=[
                    UmlOperation(
                        id="op1",
                        name="sumar",
                        return_type="int",
                        parameters=[UmlParameter(id="p1", name="a", type="int")],
                    ),
                    UmlOperation(
                        id="op2",
                        name="sumar",
                        return_type="int",
                        parameters=[UmlParameter(id="p2", name="b", type="int")],
                    ),
                ],
            )
        ],
    )
    res = validator.validate(model)
    assert not res.is_valid
    assert any(i.code == "VUML-05" for i in res.errors)


def test_spring_compatibility_multiple_inheritance():
    # Modelo UML 2.5 puro puede tener herencia múltiple, pero SpringCompatibilityValidator debe marcar ERROR
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="MultiGenModel",
        classes=[
            UmlClass(id="c1", name="Base1"),
            UmlClass(id="c2", name="Base2"),
            UmlClass(id="c3", name="Derivada"),
        ],
        generalizations=[
            UmlGeneralization(id="g1", specific_class_id="c3", general_class_id="c1"),
            UmlGeneralization(id="g2", specific_class_id="c3", general_class_id="c2"),
        ],
    )
    # En UML puro no hay ciclo, es un DAG válido
    uml_val = UMLValidator()
    assert uml_val.validate(model).is_valid

    # Pero en Spring compatibility es incompatible
    spring_val = SpringCompatibilityValidator()
    res = spring_val.validate_compatibility(model)
    assert not res.is_valid
    assert any(i.code == "VGEN-SB-01" for i in res.errors)
