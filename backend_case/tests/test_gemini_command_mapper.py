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
