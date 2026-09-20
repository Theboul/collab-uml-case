"""
Manejadores de comandos para AtributoUML (CU3).
"""

import uuid
from typing import Any, ClassVar

from backend_case.app.modeling.application.commands.base import CommandHandler
from backend_case.app.modeling.application.commands.schemas import (
    AddAttributeCommand,
    DeleteAttributeCommand,
    UpdateAttributeCommand,
)
from backend_case.app.modeling.application.commands.undo import inverso_de_edicion
from core.uml_domain.events import DomainEvent, ElementoAgregado, ElementoEliminado
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import Lienzo, UmlAttribute, UmlClass

# Campo de dominio -> clave del comando UPDATE_ATTRIBUTE (para el payload de undo).
_CLAVES_ATRIBUTO = {
    "name": "name",
    "type": "type",
    "visibility": "visibility",
    "is_static": "isStatic",
}


class AttributeCommandHandler(CommandHandler):
    """
    Gestiona el ciclo de vida de los atributos estructurales dentro de una ClaseUML.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "ADD_ATTRIBUTE",
        "CREATE_ATTRIBUTE",
        "UPDATE_ATTRIBUTE",
        "EDIT_ATTRIBUTE",
        "DELETE_ATTRIBUTE",
        "REMOVE_ATTRIBUTE",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()

        if cmd_type in ("ADD_ATTRIBUTE", "CREATE_ATTRIBUTE"):
            return self._handle_add_attribute(lienzo, payload)
        elif cmd_type in ("UPDATE_ATTRIBUTE", "EDIT_ATTRIBUTE"):
            return self._handle_update_attribute(lienzo, payload)
        elif cmd_type in ("DELETE_ATTRIBUTE", "REMOVE_ATTRIBUTE"):
            return self._handle_delete_attribute(lienzo, payload)

        raise UmlValidationError(f"Comando de atributo no reconocido: {cmd_type}")

    def _handle_add_attribute(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        # Si vino encapsulado en 'attribute', aplanar
        if "attribute" in payload and isinstance(payload["attribute"], dict):
            sub = payload["attribute"]
            payload = {**payload, **sub}

        attr_id = payload.get("id") or payload.get("attributeId")
        if attr_id:
            payload["id"] = attr_id
            payload["attributeId"] = attr_id

        cmd = AddAttributeCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        name_lower = cmd.name.strip().lower()
        if any(a.name.strip().lower() == name_lower for a in clase.attributes):
            raise UmlValidationError(
                f"Ya existe un atributo llamado '{cmd.name}' en la clase '{clase.name}'."
            )

        # Política de IDs: conservar el ID del cliente si viene provisto y no colisiona
        attr_id = str(cmd.id) if cmd.id else str(uuid.uuid4())
        if any(a.id == attr_id for a in clase.attributes):
            attr_id = str(uuid.uuid4())

        nuevo_attr = UmlAttribute(
            id=attr_id,
            name=cmd.name.strip(),
            type=cmd.type.strip(),
            visibility=cmd.visibility,
            is_static=cmd.isStatic,
        )
        clase.attributes.append(nuevo_attr)

        return ElementoAgregado(elemento_id=nuevo_attr.id, tipo="UmlAttribute"), None

    def _handle_update_attribute(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        if "id" in payload and "attributeId" not in payload:
            payload["attributeId"] = payload["id"]
        if "updates" in payload and isinstance(payload["updates"], dict):
            payload = {**payload, **payload["updates"]}

        cmd = UpdateAttributeCommand(**payload)

        attr, evento = lienzo.modelo.editar_atributo(
            cmd.classId,
            cmd.attributeId,
            nombre=cmd.name,
            tipo=cmd.type,
            visibilidad=cmd.visibility,
            is_static=cmd.isStatic,
        )
        if evento is None:
            return None, None
        return evento, inverso_de_edicion(
            evento, _CLAVES_ATRIBUTO, {"classId": cmd.classId, "attributeId": attr.id}
        )

    def _handle_delete_attribute(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        if "id" in payload and "attributeId" not in payload:
            payload["attributeId"] = payload["id"]

        cmd = DeleteAttributeCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        clase.attributes = [a for a in clase.attributes if a.id != cmd.attributeId]
        return ElementoEliminado(elemento_id=cmd.attributeId), None
