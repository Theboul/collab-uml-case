"""
Traduce la respuesta de Gemini (CU6) a la lista de comandos reales que ya usa
el editor visual, para que pasen por el mismo CommandDispatcher que ya valida
contra core/uml_domain. Este módulo no es un validador nuevo: es un traductor
de forma. Si la respuesta viene en una forma que no se puede traducir con
certeza (JSON roto, referencias rotas, acción no soportada), levanta
UmlValidationError con un mensaje que el usuario entienda como limitación
conocida, no como error críptico.

Dos formas de respuesta soportadas:
- Creación desde cero: {"classes": [...], "relationships": [...]} -- sin
  cambios respecto de la versión anterior, mapeado por
  `map_gemini_response_to_commands`.
- Operaciones sobre un modelo existente (rename/add/update/delete de clases,
  miembros y relaciones, identificadas por NOMBRE): {"operations": [...]},
  resuelto operación por operación por `resolve_operation` contra el modelo
  actual (los nombres se resuelven de a uno, en orden, para que una operación
  pueda referenciar el resultado de una anterior -- ej. renombrar una clase y
  agregarle un atributo en la misma instrucción).
"""

import re
import uuid
from typing import Any

from core.uml_domain.exceptions import UmlValidationError
from core.uml_domain.model import (
    AggregationKind,
    UmlAttribute,
    UmlClass,
    UmlDomainModel,
    UmlOperation,
)

UNRECOGNIZED_FORMAT_MESSAGE = "La respuesta de la IA no tiene un formato reconocible."

_PARAM_RE = re.compile(r"^\s*([^:]+?)\s*:\s*(.+?)\s*$")
_MULTIPLICITY_RE = re.compile(r"^(\d+(\.\.(\d+|\*))?|\*|[nmNM])$")
_ROLE_PREFIXES = ("+", "-", "#", "~")
_RELATION_TYPES = {"association", "generalization", "aggregation", "composition", "dependency"}
_RELATION_TYPES_UPPER = {t.upper() for t in _RELATION_TYPES}

_GRID_COLS = 4
_GRID_STEP_X = 240.0
_GRID_STEP_Y = 180.0
_GRID_ORIGIN = 120.0

_SUPPORTED_ACTIONS = {
    "rename_class",
    "add_attribute",
    "update_attribute",
    "delete_attribute",
    "add_operation",
    "delete_operation",
    "delete_class",
    "add_relationship",
    "delete_relationship",
    "update_relationship_type",
    "update_multiplicity",
}


# ---------------------------------------------------------------------------
# Forma de creación (sin cambios de comportamiento respecto de la versión
# anterior a esta iteración -- ver CU6 fase 1).
# ---------------------------------------------------------------------------


def map_gemini_response_to_commands(parsed: Any) -> list[tuple[str, dict[str, Any]]]:
    """
    Recibe el JSON ya parseado de la respuesta de Gemini (forma de creación) y
    devuelve la lista ordenada de comandos semánticos a despachar. Procesa
    TODAS las clases (CREATE_CLASS/ADD_ATTRIBUTE/ADD_OPERATION) antes de
    procesar cualquier relación (CREATE_RELATION), sin importar el orden en
    que 'classes' y 'relationships' aparezcan en el JSON de entrada -- son dos
    bucles secuenciales independientes, así que una relación siempre puede
    resolver sus extremos contra el conjunto completo de clases ya recorridas.
    """
    if not isinstance(parsed, dict):
        raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)

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
    class_names_by_id: dict[str, str] = {}

    # 1. Todas las clases (y sus atributos/operaciones) primero.
    for index, raw_class in enumerate(classes):
        if not isinstance(raw_class, dict):
            raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)
        name = raw_class.get("name")
        if not isinstance(name, str) or not name.strip():
            raise UmlValidationError("Una clase de la respuesta de la IA no tiene nombre.")

        class_id = str(raw_class["id"]) if raw_class.get("id") else str(uuid.uuid4())
        created_class_ids.add(class_id)
        class_names_by_id[class_id] = name.strip()

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
        multiplicities, _roles, names = _classify_relation_labels(labels)

        if rel.get("name") and str(rel["name"]).strip():
            assigned_name: str | None = str(rel["name"]).strip()
        elif len(names) == 1:
            assigned_name = names[0]
        else:
            assigned_name = None

        payload: dict[str, Any] = {
            "relationId": str(rel.get("id") or uuid.uuid4()),
            "type": rel_type.upper(),
            "sourceClassId": source_id,
            "targetClassId": target_id,
            "name": assigned_name,
        }

        if rel_type in ("association", "aggregation", "composition"):
            if len(multiplicities) != 2:
                src_m = rel.get("sourceMultiplicity")
                tgt_m = rel.get("targetMultiplicity")
                if src_m and tgt_m:
                    multiplicities = [str(src_m).strip(), str(tgt_m).strip()]
            if len(multiplicities) != 2:
                src_label = class_names_by_id.get(source_id, source_id)
                tgt_label = class_names_by_id.get(target_id, target_id)
                raise UmlValidationError(
                    f"La relación '{rel_type}' entre '{src_label}' y '{tgt_label}' "
                    f"no contiene exactamente 2 multiplicidades reconocibles en sus etiquetas "
                    f"(se encontraron {len(multiplicities)}: {multiplicities})."
                )
            payload["sourceMultiplicity"] = multiplicities[0]
            payload["targetMultiplicity"] = multiplicities[1]

        commands.append(("CREATE_RELATION", payload))

    return commands


def _classify_relation_labels(labels: list[Any]) -> tuple[list[str], list[str], list[str]]:
    """
    Clasifica las etiquetas visuales de una relación por patrón:
    - Multiplicidades: coincide con el formato UML de cardinalidad
      ('1', '*', '0..1', '0..*', '1..*', 'N..M', 'n', 'm')
    - Roles: comienza con prefijo de visibilidad UML ('+', '-', '#', '~')
    - Nombres: cualquier otra etiqueta textual que no sea rol ni multiplicidad
    """
    multiplicities: list[str] = []
    roles: list[str] = []
    names: list[str] = []

    for item in labels:
        if item is None:
            continue
        text = str(item).strip()
        if not text or text.lower() == "null":
            continue

        if _MULTIPLICITY_RE.match(text):
            multiplicities.append(text)
        elif text.startswith(_ROLE_PREFIXES):
            roles.append(text)
        else:
            names.append(text)

    return multiplicities, roles, names


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


# ---------------------------------------------------------------------------
# Forma de operaciones (CU6 fase 2): edición/eliminación sobre un modelo
# existente, identificado por nombre. Se resuelve una operación a la vez
# contra el modelo actual -- el llamador (CanvasService) es responsable de
# despachar cada comando inmediatamente después de resolverlo, para que las
# operaciones siguientes vean el efecto de las anteriores (ej. renombrar una
# clase y luego referenciarla por su nombre nuevo).
# ---------------------------------------------------------------------------


def validate_operations_shape(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Extrae y valida la forma mínima de `parsed["operations"]`."""
    operations = parsed.get("operations")
    if not isinstance(operations, list) or not operations:
        raise UmlValidationError(
            "No se reconoció ninguna operación para aplicar a partir de la instrucción."
        )
    return operations


def build_model_context(modelo: UmlDomainModel) -> dict[str, Any]:
    """
    Resumen del lienzo actual por NOMBRE (nunca por id) para darle contexto a
    Gemini al pedirle operaciones sobre el modelo existente -- sin esto, Gemini
    no tiene forma de saber qué clases/atributos/relaciones existen hoy.
    """
    classes = []
    for c in modelo.classes:
        methods = []
        for o in c.operations:
            m_dict: dict[str, Any] = {"name": o.name, "returnType": o.return_type}
            if o.parameters:
                m_dict["parameters"] = ", ".join(f"{p.name}: {p.type}" for p in o.parameters)
            methods.append(m_dict)
        classes.append(
            {
                "name": c.name,
                "attributes": [{"name": a.name, "type": a.type} for a in c.attributes],
                "methods": methods,
            }
        )

    relationships: list[dict[str, Any]] = []
    for assoc in modelo.associations:
        end1, end2 = assoc.member_ends
        src = modelo.find_classifier_by_id(end1.class_id)
        tgt = modelo.find_classifier_by_id(end2.class_id)
        rel_type = "ASSOCIATION"
        if (
            end1.aggregation_kind == AggregationKind.SHARED
            or end2.aggregation_kind == AggregationKind.SHARED
        ):
            rel_type = "AGGREGATION"
        elif (
            end1.aggregation_kind == AggregationKind.COMPOSITE
            or end2.aggregation_kind == AggregationKind.COMPOSITE
        ):
            rel_type = "COMPOSITION"
        rel_info: dict[str, Any] = {
            "type": rel_type,
            "sourceClass": src.name if src else None,
            "targetClass": tgt.name if tgt else None,
        }
        if assoc.name:
            rel_info["name"] = assoc.name
        if end1.multiplicity and end1.multiplicity.to_uml_str() != "1":
            rel_info["sourceMultiplicity"] = end1.multiplicity.to_uml_str()
        if end2.multiplicity and end2.multiplicity.to_uml_str() != "1":
            rel_info["targetMultiplicity"] = end2.multiplicity.to_uml_str()
        relationships.append(rel_info)

    for gen in modelo.generalizations:
        specific = modelo.find_classifier_by_id(gen.specific_class_id)
        general = modelo.find_classifier_by_id(gen.general_class_id)
        relationships.append(
            {
                "type": "GENERALIZATION",
                "sourceClass": specific.name if specific else None,
                "targetClass": general.name if general else None,
            }
        )
    for dep in modelo.dependencies:
        client = modelo.find_classifier_by_id(dep.client_class_id)
        supplier = modelo.find_classifier_by_id(dep.supplier_class_id)
        relationships.append(
            {
                "type": "DEPENDENCY",
                "sourceClass": client.name if client else None,
                "targetClass": supplier.name if supplier else None,
            }
        )

    return {"classes": classes, "relationships": relationships}


def resolve_operation(raw_op: Any, modelo: UmlDomainModel) -> tuple[str, dict[str, Any]]:
    """
    Resuelve UNA operación contra el modelo actual y devuelve el comando real
    (mismo tipo/payload que ya usa el editor visual) a despachar. Levanta
    UmlValidationError si el target/acción no se puede resolver con certeza
    -- nunca adivina entre varias coincidencias posibles.
    """
    if not isinstance(raw_op, dict):
        raise UmlValidationError(UNRECOGNIZED_FORMAT_MESSAGE)

    action = raw_op.get("action")
    # isinstance ANTES del "in": _SUPPORTED_ACTIONS es un set, y probar
    # pertenencia con un valor no hasheable (ej. "action": [...] o {...},
    # que Gemini podría devolver ante una instrucción ambigua) levanta
    # TypeError, no UmlValidationError -- sin esta guarda esa TypeError se
    # propagaría sin control en vez de sumarse como operación fallida.
    if not isinstance(action, str) or action not in _SUPPORTED_ACTIONS:
        raise UmlValidationError(f"Acción no soportada: '{action}'.")

    if action == "rename_class":
        clase = _resolve_class(modelo, raw_op.get("target"))
        new_name = raw_op.get("newName")
        if not new_name or not str(new_name).strip():
            raise UmlValidationError("rename_class requiere 'newName'.")
        return "UPDATE_CLASS_NAME", {"classId": clase.id, "name": str(new_name).strip()}

    if action == "add_attribute":
        clase = _resolve_class(modelo, raw_op.get("target"))
        name, type_ = raw_op.get("name"), raw_op.get("type")
        if not name or not type_:
            raise UmlValidationError("add_attribute requiere 'name' y 'type'.")
        return "ADD_ATTRIBUTE", {
            "classId": clase.id,
            "name": str(name).strip(),
            "type": str(type_).strip(),
        }

    if action == "update_attribute":
        clase = _resolve_class(modelo, raw_op.get("target"))
        attr = _resolve_attribute(clase, raw_op.get("attribute"))
        payload: dict[str, Any] = {"classId": clase.id, "attributeId": attr.id}
        if raw_op.get("newName"):
            payload["name"] = str(raw_op["newName"]).strip()
        if raw_op.get("newType"):
            payload["type"] = str(raw_op["newType"]).strip()
        if "name" not in payload and "type" not in payload:
            raise UmlValidationError("update_attribute requiere 'newName' y/o 'newType'.")
        return "UPDATE_ATTRIBUTE", payload

    if action == "delete_attribute":
        clase = _resolve_class(modelo, raw_op.get("target"))
        attr = _resolve_attribute(clase, raw_op.get("attribute"))
        return "DELETE_ATTRIBUTE", {"classId": clase.id, "attributeId": attr.id}

    if action == "add_operation":
        clase = _resolve_class(modelo, raw_op.get("target"))
        name = raw_op.get("name")
        if not name:
            raise UmlValidationError("add_operation requiere 'name'.")
        payload = {
            "classId": clase.id,
            "name": str(name).strip(),
            "returnType": str(raw_op.get("returnType") or "void").strip(),
        }
        if raw_op.get("parameters"):
            payload["parameters"] = _parse_parameters(
                raw_op["parameters"], class_name=clase.name, method_name=str(name).strip()
            )
        return "ADD_OPERATION", payload

    if action == "delete_operation":
        clase = _resolve_class(modelo, raw_op.get("target"))
        op_member = _resolve_operation_member(clase, raw_op.get("operation"))
        return "DELETE_OPERATION", {"classId": clase.id, "operationId": op_member.id}

    if action == "delete_class":
        clase = _resolve_class(modelo, raw_op.get("target"))
        return "DELETE_ELEMENTS", {"classIds": [clase.id]}

    if action == "add_relationship":
        source = _resolve_class(modelo, raw_op.get("sourceClass"))
        target = _resolve_class(modelo, raw_op.get("targetClass"))
        rel_type = _resolve_relation_type(raw_op.get("type"))
        payload = {
            "type": rel_type,
            "sourceClassId": source.id,
            "targetClassId": target.id,
        }
        if raw_op.get("name"):
            payload["name"] = str(raw_op["name"]).strip()
        if raw_op.get("sourceMultiplicity"):
            payload["sourceMultiplicity"] = str(raw_op["sourceMultiplicity"]).strip()
        if raw_op.get("targetMultiplicity"):
            payload["targetMultiplicity"] = str(raw_op["targetMultiplicity"]).strip()
        return "CREATE_RELATION", payload

    if action == "delete_relationship":
        source = _resolve_class(modelo, raw_op.get("sourceClass"))
        target = _resolve_class(modelo, raw_op.get("targetClass"))
        relation_id = _resolve_relation_id(modelo, source, target)
        return "DELETE_RELATION", {"relationId": relation_id}

    if action == "update_relationship_type":
        source = _resolve_class(modelo, raw_op.get("sourceClass"))
        target = _resolve_class(modelo, raw_op.get("targetClass"))
        relation_id = _resolve_relation_id(modelo, source, target)
        rel_type = _resolve_relation_type(raw_op.get("newType"))
        return "UPDATE_RELATION", {"relationId": relation_id, "type": rel_type}

    # update_multiplicity
    source = _resolve_class(modelo, raw_op.get("sourceClass"))
    target = _resolve_class(modelo, raw_op.get("targetClass"))
    relation_id = _resolve_relation_id(modelo, source, target)
    new_mult = raw_op.get("newMultiplicity") or raw_op.get("targetMultiplicity")
    if new_mult is not None and not isinstance(new_mult, (str, int)):
        raise UmlValidationError("update_multiplicity requiere 'newMultiplicity' válido.")
    source_mult = raw_op.get("sourceMultiplicity")
    if source_mult is not None and not isinstance(source_mult, (str, int)):
        raise UmlValidationError("update_multiplicity requiere 'sourceMultiplicity' válido.")
    if not new_mult and not source_mult:
        raise UmlValidationError("update_multiplicity requiere 'newMultiplicity'.")
    payload = {"relationId": relation_id}
    if new_mult:
        payload["targetMultiplicity"] = str(new_mult).strip()
    if source_mult:
        payload["sourceMultiplicity"] = str(source_mult).strip()
    return "UPDATE_MULTIPLICITY", payload


def _resolve_relation_type(raw_type: Any) -> str:
    rel_type = str(raw_type or "").strip().upper()
    if rel_type not in _RELATION_TYPES_UPPER:
        raise UmlValidationError(f"Tipo de relación no soportado: '{raw_type}'.")
    return rel_type


def _resolve_class(modelo: UmlDomainModel, name: Any) -> UmlClass:
    if not name or not isinstance(name, str):
        raise UmlValidationError("La operación no especifica una clase válida.")
    clase = modelo.find_classifier_by_name(name)
    if clase is None or not isinstance(clase, UmlClass):
        raise UmlValidationError(f"No existe una clase llamada '{name}'.")
    return clase


def _resolve_attribute(clase: UmlClass, name: Any) -> UmlAttribute:
    if not name or not isinstance(name, str):
        raise UmlValidationError(
            f"La operación no especifica un atributo válido para '{clase.name}'."
        )
    name_lower = name.strip().lower()
    matches = [a for a in clase.attributes if a.name.strip().lower() == name_lower]
    if not matches:
        raise UmlValidationError(f"La clase '{clase.name}' no tiene un atributo llamado '{name}'.")
    if len(matches) > 1:
        raise UmlValidationError(
            f"La clase '{clase.name}' tiene más de un atributo llamado '{name}'; "
            "no se puede determinar cuál."
        )
    return matches[0]


def _resolve_operation_member(clase: UmlClass, name: Any) -> UmlOperation:
    if not name or not isinstance(name, str):
        raise UmlValidationError(
            f"La operación no especifica un método válido para '{clase.name}'."
        )
    name_lower = name.strip().lower()
    matches = [o for o in clase.operations if o.name.strip().lower() == name_lower]
    if not matches:
        raise UmlValidationError(f"La clase '{clase.name}' no tiene un método llamado '{name}'.")
    if len(matches) > 1:
        raise UmlValidationError(
            f"La clase '{clase.name}' tiene {len(matches)} métodos llamados '{name}' "
            "(sobrecargados); no se puede determinar cuál."
        )
    return matches[0]


def _find_relation_ids_between(
    modelo: UmlDomainModel, class_id_a: str, class_id_b: str
) -> list[str]:
    matches: list[str] = []
    for assoc in modelo.associations:
        end1, end2 = assoc.member_ends
        if (end1.class_id == class_id_a and end2.class_id == class_id_b) or (
            end1.class_id == class_id_b and end2.class_id == class_id_a
        ):
            matches.append(assoc.id)
    for gen in modelo.generalizations:
        if (gen.specific_class_id == class_id_a and gen.general_class_id == class_id_b) or (
            gen.specific_class_id == class_id_b and gen.general_class_id == class_id_a
        ):
            matches.append(gen.id)
    for dep in modelo.dependencies:
        if (dep.client_class_id == class_id_a and dep.supplier_class_id == class_id_b) or (
            dep.client_class_id == class_id_b and dep.supplier_class_id == class_id_a
        ):
            matches.append(dep.id)
    for real in modelo.realizations:
        if (real.client_class_id == class_id_a and real.supplier_interface_id == class_id_b) or (
            real.client_class_id == class_id_b and real.supplier_interface_id == class_id_a
        ):
            matches.append(real.id)
    return matches


def _resolve_relation_id(modelo: UmlDomainModel, source: UmlClass, target: UmlClass) -> str:
    matches = _find_relation_ids_between(modelo, source.id, target.id)
    if not matches:
        raise UmlValidationError(
            f"No existe ninguna relación entre '{source.name}' y '{target.name}'."
        )
    if len(matches) > 1:
        raise UmlValidationError(
            f"Hay {len(matches)} relaciones entre '{source.name}' y '{target.name}'; "
            "no se puede determinar cuál modificar."
        )
    return matches[0]
