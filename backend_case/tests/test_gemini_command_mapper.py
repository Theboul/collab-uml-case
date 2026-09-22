"""
Pruebas del traductor puro Gemini -> comandos reales (CU6): forma de creación
y forma de operaciones sobre un modelo existente.
"""

import json
from pathlib import Path

import pytest

from backend_case.app.assistant.application.gemini_command_mapper import (
    build_model_context,
    map_gemini_response_to_commands,
    resolve_operation,
    validate_operations_shape,
)
from core.uml_domain.exceptions import UmlValidationError
from core.uml_domain.model import UmlAttribute, UmlDomainModel, UmlOperation

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "legacy"
    / "gemini-creation-sample.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Forma de creación (sin cambios de comportamiento)
# ---------------------------------------------------------------------------


def test_maps_creation_fixture_to_real_commands():
    parsed = _load_fixture()
    commands = map_gemini_response_to_commands(parsed)

    types = [c for c, _ in commands]
    assert types.count("CREATE_CLASS") == 2
    assert types.count("ADD_ATTRIBUTE") == 5  # 3 de Usuario + 2 de Rol
    assert types.count("ADD_OPERATION") == 1  # autenticar en Usuario
    assert types.count("CREATE_RELATION") == 1

    create_class_cmds = [p for t, p in commands if t == "CREATE_CLASS"]
    assert {c["classId"] for c in create_class_cmds} == {"c1", "c2"}

    relation_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert relation_cmd["sourceClassId"] == "c1"
    assert relation_cmd["targetClassId"] == "c2"
    assert relation_cmd["type"] == "ASSOCIATION"
    assert relation_cmd["sourceMultiplicity"] == "*"
    assert relation_cmd["targetMultiplicity"] == "1"


def test_processes_all_classes_before_any_relationship_regardless_of_json_order():
    """
    Confirma explícitamente que el orden de las claves del JSON de entrada
    ('relationships' escrito ANTES de 'classes' en el dict de origen) no
    afecta el resultado: las relaciones siempre resuelven contra el conjunto
    completo de clases ya creadas.
    """
    parsed_relationships_first = {
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "a",
                "targetId": "b",
                "labels": ["1", "1"],
            }
        ],
        "classes": [
            {"id": "a", "name": "A", "attributes": [], "methods": []},
            {"id": "b", "name": "B", "attributes": [], "methods": []},
        ],
    }
    commands = map_gemini_response_to_commands(parsed_relationships_first)
    types = [c for c, _ in commands]

    assert types.index("CREATE_RELATION") > types.index("CREATE_CLASS")
    assert types.count("CREATE_CLASS") == 2
    relation_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert relation_cmd["sourceClassId"] == "a"
    assert relation_cmd["targetClassId"] == "b"


def test_classifies_labels_by_pattern_extracting_multiplicities_and_name():
    """
    Caso real capturado: las etiquetas vienen mezcladas con el nombre de la
    asociación, roles con visibilidad UML y multiplicidades. Se debe clasificar
    por patrón, asignando la primera multiplicidad a source y la segunda a target,
    y el texto restante como nombre.
    """
    parsed = {
        "classes": [
            {"id": "c1", "name": "ClaseA", "attributes": [], "methods": []},
            {"id": "c2", "name": "ClaseB", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["Association B", "+role c", "*", "+role a", "0..1"],
            }
        ],
    }
    commands = map_gemini_response_to_commands(parsed)
    rel_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert rel_cmd["sourceMultiplicity"] == "*"
    assert rel_cmd["targetMultiplicity"] == "0..1"
    assert rel_cmd["name"] == "Association B"


def test_classifies_labels_with_identical_multiplicities_many_to_many():
    """
    Caso real capturado (relación many-to-many *..*):
    labels = ["+role b", "*", "Association A", "+role a", "*"].
    Confirma que las dos multiplicidades idénticas '*' y '*' se preservan
    y asignan correctamente a sourceMultiplicity y targetMultiplicity sin
    ser deduplicadas ni rechazadas.
    """
    parsed = {
        "classes": [
            {"id": "c1", "name": "ClaseB", "attributes": [], "methods": []},
            {"id": "c2", "name": "ClaseA", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["+role b", "*", "Association A", "+role a", "*"],
            }
        ],
    }
    commands = map_gemini_response_to_commands(parsed)
    rel_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert rel_cmd["sourceMultiplicity"] == "*"
    assert rel_cmd["targetMultiplicity"] == "*"
    assert rel_cmd["name"] == "Association A"


def test_map_edges_to_relationships_preserves_identical_multiplicities():
    """
    Confirma que _map_edges_to_relationships no deduplica labels con dict.fromkeys(),
    permitiendo relaciones many-to-many (*..*) o 1..1 donde las etiquetas de multiplicidad
    son idénticas en ambos extremos.
    """
    from backend_case.app.legacy.services_gemini import _map_edges_to_relationships

    raw_gemini = {
        "nodes": [
            {"id": "c1", "name": "ClaseB", "attributes": [], "methods": []},
            {"id": "c2", "name": "ClaseA", "attributes": [], "methods": []},
        ],
        "edges_raw": [
            {
                "id": "e1",
                "sourceName": "ClaseB",
                "targetName": "ClaseA",
                "head": {"shape": "none"},
                "tail": {"shape": "none"},
                "line": {"style": "solid"},
                "labels": ["+role b", "*", "Association A", "+role a", "*"],
            }
        ],
    }
    result = _map_edges_to_relationships(raw_gemini)
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["labels"] == [
        "+role b",
        "*",
        "Association A",
        "+role a",
        "*",
    ]


def test_map_edges_to_relationships_deduplicates_repeated_edges_without_doubling_labels():
    """
    Si Gemini reporta la misma arista dos veces en edges_raw (mismo rel_key o
    inverso, ej. A->B y B->A con ["*", "0..1"]), no debe hacer .extend()
    duplicando las etiquetas a 4 elementos, sino tomar una sola aparición
    completa y permitir que map_gemini_response_to_commands la procese.
    """
    from backend_case.app.legacy.services_gemini import _map_edges_to_relationships

    raw_gemini = {
        "nodes": [
            {"id": "c1", "name": "ClaseA", "attributes": [], "methods": []},
            {"id": "c2", "name": "ClaseB", "attributes": [], "methods": []},
        ],
        "edges_raw": [
            {
                "id": "e1",
                "sourceName": "ClaseA",
                "targetName": "ClaseB",
                "head": {"shape": "none"},
                "tail": {"shape": "none"},
                "line": {"style": "solid"},
                "labels": ["*", "0..1"],
            },
            {
                "id": "e2",
                "sourceName": "ClaseA",
                "targetName": "ClaseB",
                "head": {"shape": "none"},
                "tail": {"shape": "none"},
                "line": {"style": "solid"},
                "labels": ["*", "0..1"],
            },
        ],
    }
    result = _map_edges_to_relationships(raw_gemini)
    assert len(result["relationships"]) == 1
    assert result["relationships"][0]["labels"] == ["*", "0..1"]

    commands = map_gemini_response_to_commands(result)
    rel_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert rel_cmd["sourceMultiplicity"] == "*"
    assert rel_cmd["targetMultiplicity"] == "0..1"


def test_rejects_association_without_exactly_two_multiplicities():
    """
    Si una asociación/agregación/composición no define exactamente 2 multiplicidades
    reconocibles en sus labels (ej. 0, 1 o 3), levanta UmlValidationError controlado,
    nunca un 500 ni IndexError.
    """
    # Caso 0 multiplicidades
    parsed_zero = {
        "classes": [
            {"id": "c1", "name": "A", "attributes": [], "methods": []},
            {"id": "c2", "name": "B", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["Association B", "+role c", "+role a"],
            }
        ],
    }
    with pytest.raises(UmlValidationError) as exc_zero:
        map_gemini_response_to_commands(parsed_zero)
    assert "no contiene exactamente 2 multiplicidades" in str(exc_zero.value)
    assert "'A' y 'B'" in str(exc_zero.value)

    # Caso 1 multiplicidad
    parsed_one = {
        "classes": [
            {"id": "c1", "name": "A", "attributes": [], "methods": []},
            {"id": "c2", "name": "B", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["1"],
            }
        ],
    }
    with pytest.raises(UmlValidationError) as exc_one:
        map_gemini_response_to_commands(parsed_one)
    assert "no contiene exactamente 2 multiplicidades" in str(exc_one.value)

    # Caso 3 multiplicidades
    parsed_three = {
        "classes": [
            {"id": "c1", "name": "A", "attributes": [], "methods": []},
            {"id": "c2", "name": "B", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["1", "*", "0..1"],
            }
        ],
    }
    with pytest.raises(UmlValidationError) as exc_three:
        map_gemini_response_to_commands(parsed_three)
    assert "no contiene exactamente 2 multiplicidades" in str(exc_three.value)


def test_relation_with_multiple_name_candidates_leaves_name_unassigned():
    """
    Si hay más de 1 candidato a nombre de asociación en labels (y no viene
    un name explícito en el dict), se deja name como None para no adivinar.
    """
    parsed = {
        "classes": [
            {"id": "c1", "name": "A", "attributes": [], "methods": []},
            {"id": "c2", "name": "B", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["Nombre Uno", "Nombre Dos", "1", "*"],
            }
        ],
    }
    commands = map_gemini_response_to_commands(parsed)
    rel_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert rel_cmd["sourceMultiplicity"] == "1"
    assert rel_cmd["targetMultiplicity"] == "*"
    assert rel_cmd["name"] is None


def test_generalization_does_not_require_nor_emit_multiplicities():
    """
    En UML (y en UmlGeneralization), la herencia no tiene multiplicidades.
    El mapper no exige 2 multiplicidades ni emite sourceMultiplicity / targetMultiplicity.
    """
    parsed = {
        "classes": [
            {"id": "c1", "name": "Subclase", "attributes": [], "methods": []},
            {"id": "c2", "name": "Superclase", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "generalization",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": [],
            }
        ],
    }
    commands = map_gemini_response_to_commands(parsed)
    rel_cmd = next(p for t, p in commands if t == "CREATE_RELATION")
    assert rel_cmd["type"] == "GENERALIZATION"
    assert "sourceMultiplicity" not in rel_cmd
    assert "targetMultiplicity" not in rel_cmd


def test_original_editado_shape_now_rejected_as_unrecognized():
    """
    El formato {"original","editado"} (edición) y el de "eliminar": true por
    elemento (eliminación) quedaron retirados en esta iteración -- Gemini ya
    no los pide (services_gemini.py los reemplazó por 'operations'). Si de
    todos modos aparecieran, el mapper los trata como forma no reconocida en
    vez de una creación mal interpretada.
    """
    parsed = {"original": {"classes": []}, "editado": {"editado": True}}
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands(parsed)


def test_rejects_relationship_referencing_unknown_class():
    parsed = {
        "classes": [{"id": "c1", "name": "Usuario", "attributes": [], "methods": []}],
        "relationships": [
            {
                "id": "r1",
                "type": "association",
                "sourceId": "c1",
                "targetId": "c-inexistente",
                "labels": ["1", "1"],
            }
        ],
    }
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands(parsed)


def test_rejects_unsupported_relation_type():
    parsed = {
        "classes": [
            {"id": "c1", "name": "A", "attributes": [], "methods": []},
            {"id": "c2", "name": "B", "attributes": [], "methods": []},
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "friendship",
                "sourceId": "c1",
                "targetId": "c2",
                "labels": ["1", "1"],
            }
        ],
    }
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands(parsed)


def test_rejects_malformed_method_parameters():
    parsed = {
        "classes": [
            {
                "id": "c1",
                "name": "Usuario",
                "attributes": [],
                "methods": [
                    {
                        "name": "autenticar",
                        "parameters": "clave sin dos puntos",
                        "returnType": "Boolean",
                    }
                ],
            }
        ],
        "relationships": [],
    }
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands(parsed)


def test_rejects_empty_response():
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands({"classes": [], "relationships": []})


def test_rejects_non_dict_response():
    with pytest.raises(UmlValidationError):
        map_gemini_response_to_commands(["no", "es", "un", "objeto"])


# ---------------------------------------------------------------------------
# Forma de operaciones (CU6 fase 2): edición/eliminación por nombre
# ---------------------------------------------------------------------------


@pytest.fixture
def modelo() -> UmlDomainModel:
    m = UmlDomainModel()
    usuario, _ = m.agregar_clase("Usuario")
    usuario.attributes.append(UmlAttribute(name="email", type="String"))
    usuario.operations.append(UmlOperation(name="autenticar", return_type="Boolean"))
    rol, _ = m.agregar_clase("Rol")
    m.agregar_asociacion(origen_id=usuario.id, destino_id=rol.id)
    return m


def test_resolve_rename_class(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    cmd_type, payload = resolve_operation(
        {"action": "rename_class", "target": "Usuario", "newName": "Cliente"}, modelo
    )
    assert cmd_type == "UPDATE_CLASS_NAME"
    assert payload == {"classId": usuario.id, "name": "Cliente"}


def test_resolve_add_attribute(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    cmd_type, payload = resolve_operation(
        {"action": "add_attribute", "target": "Usuario", "name": "telefono", "type": "String"},
        modelo,
    )
    assert cmd_type == "ADD_ATTRIBUTE"
    assert payload == {"classId": usuario.id, "name": "telefono", "type": "String"}


def test_resolve_update_attribute(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    email_attr = next(a for a in usuario.attributes if a.name == "email")
    cmd_type, payload = resolve_operation(
        {
            "action": "update_attribute",
            "target": "Usuario",
            "attribute": "email",
            "newType": "Text",
        },
        modelo,
    )
    assert cmd_type == "UPDATE_ATTRIBUTE"
    assert payload == {"classId": usuario.id, "attributeId": email_attr.id, "type": "Text"}


def test_resolve_update_attribute_requires_new_value():
    m = UmlDomainModel()
    usuario, _ = m.agregar_clase("Usuario")
    usuario.attributes.append(UmlAttribute(name="email", type="String"))
    with pytest.raises(UmlValidationError):
        resolve_operation(
            {"action": "update_attribute", "target": "Usuario", "attribute": "email"}, m
        )


def test_resolve_delete_attribute(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    email_attr = next(a for a in usuario.attributes if a.name == "email")
    cmd_type, payload = resolve_operation(
        {"action": "delete_attribute", "target": "Usuario", "attribute": "email"}, modelo
    )
    assert cmd_type == "DELETE_ATTRIBUTE"
    assert payload == {"classId": usuario.id, "attributeId": email_attr.id}


def test_resolve_add_operation(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    cmd_type, payload = resolve_operation(
        {
            "action": "add_operation",
            "target": "Usuario",
            "name": "validar",
            "returnType": "Boolean",
        },
        modelo,
    )
    assert cmd_type == "ADD_OPERATION"
    assert payload == {"classId": usuario.id, "name": "validar", "returnType": "Boolean"}


def test_resolve_delete_operation(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    autenticar = next(o for o in usuario.operations if o.name == "autenticar")
    cmd_type, payload = resolve_operation(
        {"action": "delete_operation", "target": "Usuario", "operation": "autenticar"}, modelo
    )
    assert cmd_type == "DELETE_OPERATION"
    assert payload == {"classId": usuario.id, "operationId": autenticar.id}


def test_resolve_delete_class(modelo):
    rol = modelo.find_classifier_by_name("Rol")
    cmd_type, payload = resolve_operation({"action": "delete_class", "target": "Rol"}, modelo)
    assert cmd_type == "DELETE_ELEMENTS"
    assert payload == {"classIds": [rol.id]}


def test_resolve_add_relationship(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    rol = modelo.find_classifier_by_name("Rol")
    cmd_type, payload = resolve_operation(
        {
            "action": "add_relationship",
            "sourceClass": "Usuario",
            "targetClass": "Rol",
            "type": "AGGREGATION",
        },
        modelo,
    )
    assert cmd_type == "CREATE_RELATION"
    assert payload == {"type": "AGGREGATION", "sourceClassId": usuario.id, "targetClassId": rol.id}


def test_resolve_delete_relationship(modelo):
    existing_assoc = modelo.associations[0]
    cmd_type, payload = resolve_operation(
        {"action": "delete_relationship", "sourceClass": "Usuario", "targetClass": "Rol"}, modelo
    )
    assert cmd_type == "DELETE_RELATION"
    assert payload == {"relationId": existing_assoc.id}


def test_resolve_update_relationship_type(modelo):
    existing_assoc = modelo.associations[0]
    cmd_type, payload = resolve_operation(
        {
            "action": "update_relationship_type",
            "sourceClass": "Usuario",
            "targetClass": "Rol",
            "newType": "AGGREGATION",
        },
        modelo,
    )
    assert cmd_type == "UPDATE_RELATION"
    assert payload == {"relationId": existing_assoc.id, "type": "AGGREGATION"}


def test_resolve_update_multiplicity(modelo):
    existing_assoc = modelo.associations[0]
    cmd_type, payload = resolve_operation(
        {
            "action": "update_multiplicity",
            "sourceClass": "Usuario",
            "targetClass": "Rol",
            "newMultiplicity": "0..*",
        },
        modelo,
    )
    assert cmd_type == "UPDATE_MULTIPLICITY"
    assert payload == {"relationId": existing_assoc.id, "targetMultiplicity": "0..*"}


def test_resolve_operation_rejects_unsupported_action(modelo):
    with pytest.raises(UmlValidationError):
        resolve_operation({"action": "teleport_class", "target": "Usuario"}, modelo)


def test_resolve_operation_rejects_non_hashable_action_as_clean_error_not_typeerror(modelo):
    """
    Antes: 'action not in _SUPPORTED_ACTIONS' con un valor no hasheable
    (ej. una lista, si Gemini responde una instrucción ambigua con esa
    forma) levantaba TypeError sin control en vez de UmlValidationError.
    """
    with pytest.raises(UmlValidationError):
        resolve_operation({"action": ["rename_class"]}, modelo)
    with pytest.raises(UmlValidationError):
        resolve_operation({"action": {"nested": "dict"}}, modelo)


def test_resolve_update_multiplicity_rejects_non_string_value(modelo):
    """
    Antes: 'newMultiplicity' con un tipo no-string/int (ej. una lista) pasaba
    el chequeo 'if not new_mult' sin problema (una lista no vacía es truthy)
    y se aceptaba en silencio -- el error recién aparecía río abajo, en el
    parser de multiplicidad del dispatcher, con un mensaje menos claro.
    """
    with pytest.raises(UmlValidationError):
        resolve_operation(
            {
                "action": "update_multiplicity",
                "sourceClass": "Usuario",
                "targetClass": "Rol",
                "newMultiplicity": [1, 2],
            },
            modelo,
        )


def test_resolve_operation_rejects_unknown_class_target(modelo):
    with pytest.raises(UmlValidationError):
        resolve_operation({"action": "delete_class", "target": "Inexistente"}, modelo)


def test_resolve_relationship_action_rejects_missing_relation(modelo):
    m = UmlDomainModel()
    m.agregar_clase("Solitaria")
    m.agregar_clase("OtraSolitaria")
    with pytest.raises(UmlValidationError):
        resolve_operation(
            {
                "action": "delete_relationship",
                "sourceClass": "Solitaria",
                "targetClass": "OtraSolitaria",
            },
            m,
        )


def test_resolve_relationship_action_ambiguous_pair_rejected(modelo):
    """Una segunda relación entre las mismas dos clases es ambigüedad real: no adivinar cuál."""
    usuario = modelo.find_classifier_by_name("Usuario")
    rol = modelo.find_classifier_by_name("Rol")
    modelo.agregar_generalizacion(usuario.id, rol.id)
    with pytest.raises(UmlValidationError):
        resolve_operation(
            {"action": "delete_relationship", "sourceClass": "Usuario", "targetClass": "Rol"},
            modelo,
        )


def test_resolve_delete_operation_ambiguous_overload_rejected(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    usuario.operations.append(UmlOperation(name="autenticar", return_type="String"))
    with pytest.raises(UmlValidationError):
        resolve_operation(
            {"action": "delete_operation", "target": "Usuario", "operation": "autenticar"}, modelo
        )


def test_validate_operations_shape_rejects_empty_list():
    with pytest.raises(UmlValidationError):
        validate_operations_shape({"operations": []})


def test_validate_operations_shape_rejects_non_list():
    with pytest.raises(UmlValidationError):
        validate_operations_shape({"operations": "no es una lista"})


def test_build_model_context_includes_names_and_relation_types(modelo):
    context = build_model_context(modelo)
    assert {
        "name": "Usuario",
        "attributes": [{"name": "email", "type": "String"}],
        "methods": [{"name": "autenticar", "returnType": "Boolean"}],
    } in context["classes"]
    assert {"type": "ASSOCIATION", "sourceClass": "Usuario", "targetClass": "Rol"} in context[
        "relationships"
    ]


def test_resolve_add_operation_with_parameters(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    cmd_type, payload = resolve_operation(
        {
            "action": "add_operation",
            "target": "Usuario",
            "name": "login",
            "returnType": "Boolean",
            "parameters": "email: String, clave: String",
        },
        modelo,
    )
    assert cmd_type == "ADD_OPERATION"
    assert payload == {
        "classId": usuario.id,
        "name": "login",
        "returnType": "Boolean",
        "parameters": [
            {"name": "email", "type": "String"},
            {"name": "clave", "type": "String"},
        ],
    }


def test_resolve_add_relationship_with_name_and_multiplicities(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    rol = modelo.find_classifier_by_name("Rol")
    cmd_type, payload = resolve_operation(
        {
            "action": "add_relationship",
            "sourceClass": "Usuario",
            "targetClass": "Rol",
            "type": "association",
            "name": "tiene_rol",
            "sourceMultiplicity": "*",
            "targetMultiplicity": "1..*",
        },
        modelo,
    )
    assert cmd_type == "CREATE_RELATION"
    assert payload["sourceClassId"] == usuario.id
    assert payload["targetClassId"] == rol.id
    assert payload["name"] == "tiene_rol"
    assert payload["sourceMultiplicity"] == "*"
    assert payload["targetMultiplicity"] == "1..*"


def test_resolve_reflexive_relationship_operation(modelo):
    usuario = modelo.find_classifier_by_name("Usuario")
    cmd_type, payload = resolve_operation(
        {
            "action": "add_relationship",
            "sourceClass": "Usuario",
            "targetClass": "Usuario",
            "type": "association",
            "name": "supervisa",
            "sourceMultiplicity": "0..1",
            "targetMultiplicity": "*",
        },
        modelo,
    )
    assert cmd_type == "CREATE_RELATION"
    assert payload["sourceClassId"] == usuario.id
    assert payload["targetClassId"] == usuario.id
    assert payload["name"] == "supervisa"

