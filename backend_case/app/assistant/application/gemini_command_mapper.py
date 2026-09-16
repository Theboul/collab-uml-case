"""
Traduce la respuesta de Gemini (CU6, forma de creación) a la lista de comandos
reales que ya usa el editor visual (CREATE_CLASS, ADD_ATTRIBUTE, ADD_OPERATION,
CREATE_RELATION), para que pasen por el mismo CommandDispatcher que ya valida
contra core/uml_domain. Este módulo no es un validador nuevo: es un traductor
de forma. Si la respuesta viene en una forma que no se puede traducir con
certeza (edición, eliminación, JSON roto, referencias rotas), levanta
UmlValidationError con un mensaje que el usuario entienda como limitación
conocida, no como error críptico.
"""

import re
import uuid
from typing import Any

from core.uml_domain.exceptions import UmlValidationError

EDIT_OR_DELETE_MESSAGE = (
    "Todavía no se soportan ediciones ni eliminaciones por texto/voz, "
    "solo creación de elementos nuevos."
)
UNRECOGNIZED_FORMAT_MESSAGE = "La respuesta de la IA no tiene un formato reconocible."

_PARAM_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.+?)\s*$")
_RELATION_TYPES = {"association", "generalization", "aggregation", "composition", "dependency"}

_GRID_COLS = 4
_GRID_STEP_X = 240.0
_GRID_STEP_Y = 180.0
_GRID_ORIGIN = 120.0


def map_gemini_response_to_commands(parsed: Any) -> list[tuple[str, dict[str, Any]]]:
    """
    Recibe el JSON ya parseado de la respuesta de Gemini y devuelve la lista
    ordenada de comandos semánticos a despachar. Procesa TODAS las clases
    (CREATE_CLASS/ADD_ATTRIBUTE/ADD_OPERATION) antes de procesar cualquier
    relación (CREATE_RELATION), sin importar el orden en que 'classes' y
    'relationships' aparezcan en el JSON de entrada -- son dos bucles
    secuenciales independientes, así que una relación siempre puede resolver
    sus extremos contra el conjunto completo de clases ya recorridas.
    """
    if not isinstance(parsed, dict):
        raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)

    if "original" in parsed or "editado" in parsed or _tiene_marca_eliminar(parsed):
        raise UmlValidationError(EDIT_OR_DELETE_MESSAGE)

    classes = parsed.get("classes", [])
    relationships = parsed.get("relationships", [])
    if not isinstance(classes, list) or not isinstance(relationships, list):
        raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)
    if not classes and not relationships:
        raise UmlValidationError(
            "No se reconoció ningún elemento para crear a partir de la instrucción."
        )

    commands: list[tuple[str, dict[str, Any]]] = []
    created_class_ids: set[str] = set()

    # 1. Todas las clases (y sus atributos/operaciones) primero.
    for index, raw_class in enumerate(classes):
        if not isinstance(raw_class, dict):
            raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)
        name = raw_class.get("name")
        if not isinstance(name, str) or not name.strip():
            raise UmlValidationError("Una clase de la respuesta de la IA no tiene nombre.")

        class_id = str(raw_class["id"]) if raw_class.get("id") else str(uuid.uuid4())
        created_class_ids.add(class_id)

        x = _GRID_ORIGIN + (index % _GRID_COLS) * _GRID_STEP_X
        y = _GRID_ORIGIN + (index // _GRID_COLS) * _GRID_STEP_Y
        commands.append(
            (
                "CREATE_CLASS",
                {"classId": class_id, "name": name.strip(), "isAbstract": False, "x": x, "y": y},
            )
        )

        for attr in raw_class.get("attributes") or []:
            if not isinstance(attr, dict) or not attr.get("name") or not attr.get("type"):
                raise UmlValidationError(
                    f"Un atributo de la clase '{name}' no tiene nombre y tipo completos."
                )
            commands.append(
                (
                    "ADD_ATTRIBUTE",
                    {
                        "classId": class_id,
                        "name": str(attr["name"]).strip(),
                        "type": str(attr["type"]).strip(),
                    },
                )
            )

        for method in raw_class.get("methods") or []:
            if not isinstance(method, dict) or not method.get("name"):
                raise UmlValidationError(f"Un método de la clase '{name}' no tiene nombre.")
            params = _parse_parameters(
                method.get("parameters"), class_name=name, method_name=method["name"]
            )
            commands.append(
                (
                    "ADD_OPERATION",
                    {
                        "classId": class_id,
                        "name": str(method["name"]).strip(),
                        "returnType": str(method.get("returnType") or "void").strip(),
                        "parameters": params,
                    },
                )
            )

    # 2. Recién ahora las relaciones, que pueden referenciar cualquier clase del paso 1.
    for rel in relationships:
        if not isinstance(rel, dict):
            raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)
        rel_type = str(rel.get("type") or "").strip().lower()
        if rel_type not in _RELATION_TYPES:
            raise UmlValidationError(f"Tipo de relación no soportado: '{rel.get('type')}'.")

        source_id = str(rel.get("sourceId") or "")
        target_id = str(rel.get("targetId") or "")
        if source_id not in created_class_ids or target_id not in created_class_ids:
            raise UmlValidationError(
                "Una relación de la respuesta de la IA referencia una clase que no "
                "existe en la misma respuesta."
            )

        labels = rel.get("labels") or []
        source_mult = str(labels[0]) if len(labels) > 0 and labels[0] else "1"
        target_mult = str(labels[1]) if len(labels) > 1 and labels[1] else "1"

        commands.append(
            (
                "CREATE_RELATION",
                {
                    "relationId": str(rel.get("id") or uuid.uuid4()),
                    "type": rel_type.upper(),
                    "sourceClassId": source_id,
                    "targetClassId": target_id,
                    "sourceMultiplicity": source_mult,
                    "targetMultiplicity": target_mult,
                    "name": rel.get("name"),
                },
            )
        )

    return commands


def _tiene_marca_eliminar(parsed: dict[str, Any]) -> bool:
    for clase in parsed.get("classes") or []:
        if not isinstance(clase, dict):
            continue
        if clase.get("eliminar"):
            return True
        for attr in clase.get("attributes") or []:
            if isinstance(attr, dict) and attr.get("eliminar"):
                return True
        for metodo in clase.get("methods") or []:
            if isinstance(metodo, dict) and metodo.get("eliminar"):
                return True
    for rel in parsed.get("relationships") or []:
        if isinstance(rel, dict) and rel.get("eliminar"):
            return True
    return False


def _parse_parameters(raw: Any, class_name: str, method_name: str) -> list[dict[str, str]]:
    if not raw:
        return []
    if not isinstance(raw, str):
        raise UmlValidationError(
            f"Los parámetros del método '{method_name}' de '{class_name}' "
            "no tienen un formato reconocible."
        )
    result: list[dict[str, str]] = []
    for segment in raw.split(","):
        segment = segment.strip()
        if not segment:
            continue
        match = _PARAM_RE.match(segment)
        if not match:
            raise UmlValidationError(
                f"El parámetro '{segment}' del método '{method_name}' de '{class_name}' "
                "no tiene el formato 'nombre: tipo'."
            )
        result.append({"name": match.group(1).strip(), "type": match.group(2).strip()})
    return result
