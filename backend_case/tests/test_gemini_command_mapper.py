"""
Pruebas del traductor puro Gemini -> comandos reales (CU6).
"""

import json
from pathlib import Path

import pytest

from backend_case.app.assistant.application.gemini_command_mapper import (
    EDIT_OR_DELETE_MESSAGE,
    map_gemini_response_to_commands,
)
from core.uml_domain.exceptions import UmlValidationError

FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "fixtures"
    / "legacy"
    / "gemini-creation-sample.json"
)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


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


def test_rejects_edit_shape_with_clear_limitation_message():
    parsed = {"original": {"classes": []}, "editado": {"editado": True}}
    with pytest.raises(UmlValidationError) as exc_info:
        map_gemini_response_to_commands(parsed)
    assert str(exc_info.value) == EDIT_OR_DELETE_MESSAGE


def test_rejects_delete_marked_elements_with_clear_limitation_message():
    parsed = {"classes": [{"name": "Usuario", "eliminar": True}], "relationships": []}
    with pytest.raises(UmlValidationError) as exc_info:
        map_gemini_response_to_commands(parsed)
    assert str(exc_info.value) == EDIT_OR_DELETE_MESSAGE


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
