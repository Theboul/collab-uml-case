"""
Manejadores de comandos para ParametroUML (CU3).
"""

import uuid
from typing import Any, ClassVar

from backend_case.app.modeling.application.commands.base import CommandHandler
from backend_case.app.modeling.application.commands.schemas import (
    AddParameterCommand,
    DeleteParameterCommand,
    UpdateParameterCommand,
)
from core.uml_domain.events import DomainEvent, ElementoAgregado, ElementoEliminado
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import (
    Lienzo,
    ParameterDirectionKind,
    UmlClass,
    UmlParameter,
)


class ParameterCommandHandler(CommandHandler):
    """
    Gestiona el ciclo de vida de los parámetros formales dentro de una OperacionUML.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "ADD_PARAMETER",
        "CREATE_PARAMETER",
        "UPDATE_PARAMETER",
        "EDIT_PARAMETER",
        "DELETE_PARAMETER",
        "REMOVE_PARAMETER",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()

        if cmd_type in ("ADD_PARAMETER", "CREATE_PARAMETER"):
            return self._handle_add_parameter(lienzo, payload)
        elif cmd_type in ("UPDATE_PARAMETER", "EDIT_PARAMETER"):
            return self._handle_update_parameter(lienzo, payload)
        elif cmd_type in ("DELETE_PARAMETER", "REMOVE_PARAMETER"):
            return self._handle_delete_parameter(lienzo, payload)

        raise UmlValidationError(f"Comando de parámetro no reconocido: {cmd_type}")

    def _handle_add_parameter(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        if "parameter" in payload and isinstance(payload["parameter"], dict):
            sub = payload["parameter"]
            payload = {**payload, **sub}

        p_id = payload.get("id") or payload.get("parameterId")
        if p_id:
            payload["id"] = p_id
            payload["parameterId"] = p_id

        cmd = AddParameterCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        op = next((o for o in clase.operations if o.id == cmd.operationId), None)
        if op is None:
            raise ElementoNoEncontrado(
                f"Operación con ID '{cmd.operationId}' no encontrada en la clase '{clase.name}'."
            )

        param_name_lower = cmd.name.strip().lower()
        if any(p.name.strip().lower() == param_name_lower for p in op.parameters):
            raise UmlValidationError(
                f"Ya existe un parámetro llamado '{cmd.name}' en la operación '{op.name}'."
            )

        param_id = str(cmd.id) if cmd.id else str(uuid.uuid4())
        if any(p.id == param_id for p in op.parameters):
            param_id = str(uuid.uuid4())

        nuevo_param = UmlParameter(
            id=param_id,
            name=cmd.name.strip(),
            type=cmd.type.strip(),
            direction=ParameterDirectionKind.IN,
        )
        op.parameters.append(nuevo_param)

        return ElementoAgregado(elemento_id=nuevo_param.id, tipo="UmlParameter"), None

    def _handle_update_parameter(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, None]:
        if "id" in payload and "parameterId" not in payload:
            payload["parameterId"] = payload["id"]
        if "updates" in payload and isinstance(payload["updates"], dict):
            payload = {**payload, **payload["updates"]}

        cmd = UpdateParameterCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        op = next((o for o in clase.operations if o.id == cmd.operationId), None)
        if op is None:
            raise ElementoNoEncontrado(
                f"Operación con ID '{cmd.operationId}' no encontrada en la clase '{clase.name}'."
            )

        param = next((p for p in op.parameters if p.id == cmd.parameterId), None)
        if param is None:
            raise ElementoNoEncontrado(
                f"Parámetro con ID '{cmd.parameterId}' no encontrado en la operación '{op.name}'."
            )

        if cmd.name is not None:
            clean_name = cmd.name.strip()
            clean_lower = clean_name.lower()
            if any(p.name.strip().lower() == clean_lower and p.id != cmd.parameterId for p in op.parameters):
                raise UmlValidationError(
                    f"Ya existe otro parámetro llamado '{clean_name}' en la operación '{op.name}'."
                )
            param.name = clean_name

        if cmd.type is not None:
            param.type = cmd.type.strip()

        return None, None

    def _handle_delete_parameter(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        if "id" in payload and "parameterId" not in payload:
            payload["parameterId"] = payload["id"]

        cmd = DeleteParameterCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        op = next((o for o in clase.operations if o.id == cmd.operationId), None)
        if op is None:
            raise ElementoNoEncontrado(
                f"Operación con ID '{cmd.operationId}' no encontrada en la clase '{clase.name}'."
            )

        op.parameters = [p for p in op.parameters if p.id != cmd.parameterId]
        return ElementoEliminado(elemento_id=cmd.parameterId), None
