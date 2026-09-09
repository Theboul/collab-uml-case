"""
Manejadores de comandos para OperacionUML (CU3).
"""

import uuid
from typing import Any, ClassVar

from backend_case.app.modeling.application.commands.base import CommandHandler
from backend_case.app.modeling.application.commands.schemas import (
    AddOperationCommand,
    DeleteOperationCommand,
    UpdateOperationCommand,
)
from core.uml_domain.events import DomainEvent, ElementoAgregado, ElementoEliminado
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import (
    Lienzo,
    ParameterDirectionKind,
    UmlClass,
    UmlOperation,
    UmlParameter,
)


def _compute_op_signature(op: UmlOperation | AddOperationCommand | UpdateOperationCommand) -> tuple[str, tuple[str, ...]]:
    name = op.name.strip().lower() if op.name else ""
    param_types = tuple(p.type.strip().lower() for p in (op.parameters or []))
    return (name, param_types)


class OperationCommandHandler(CommandHandler):
    """
    Gestiona el ciclo de vida de las operaciones (métodos) y sobrecarga por firma.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "ADD_OPERATION",
        "CREATE_OPERATION",
        "UPDATE_OPERATION",
        "EDIT_OPERATION",
        "DELETE_OPERATION",
        "REMOVE_OPERATION",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()

        if cmd_type in ("ADD_OPERATION", "CREATE_OPERATION"):
            return self._handle_add_operation(lienzo, payload)
        elif cmd_type in ("UPDATE_OPERATION", "EDIT_OPERATION"):
            return self._handle_update_operation(lienzo, payload)
        elif cmd_type in ("DELETE_OPERATION", "REMOVE_OPERATION"):
            return self._handle_delete_operation(lienzo, payload)

        raise UmlValidationError(f"Comando de operación no reconocido: {cmd_type}")

    def _handle_add_operation(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        if "operation" in payload and isinstance(payload["operation"], dict):
            sub = payload["operation"]
            payload = {**payload, **sub}

        op_id = payload.get("id") or payload.get("operationId")
        if op_id:
            payload["id"] = op_id
            payload["operationId"] = op_id

        cmd = AddOperationCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        new_sig = _compute_op_signature(cmd)
        for existing_op in clase.operations:
            if _compute_op_signature(existing_op) == new_sig:
                raise UmlValidationError(
                    f"Ya existe una operación con la firma '{cmd.name}({', '.join(new_sig[1])})' en la clase '{clase.name}'."
                )

        op_id = str(cmd.id) if cmd.id else str(uuid.uuid4())
        if any(o.id == op_id for o in clase.operations):
            op_id = str(uuid.uuid4())

        params_domain: list[UmlParameter] = []
        for p in cmd.parameters:
            pid = str(p.id) if getattr(p, "id", None) else str(uuid.uuid4())
            params_domain.append(
                UmlParameter(
                    id=pid,
                    name=p.name.strip(),
                    type=p.type.strip(),
                    direction=ParameterDirectionKind(p.direction) if hasattr(p, "direction") else ParameterDirectionKind.IN,
                    default_value=p.defaultValue,
                )
            )

        nueva_op = UmlOperation(
            id=op_id,
            name=cmd.name.strip(),
            return_type=cmd.returnType.strip(),
            visibility=cmd.visibility,
            parameters=params_domain,
            is_static=cmd.isStatic,
            is_abstract=cmd.isAbstract,
        )
        clase.operations.append(nueva_op)

        return ElementoAgregado(elemento_id=nueva_op.id, tipo="UmlOperation"), None

    def _handle_update_operation(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, None]:
        if "id" in payload and "operationId" not in payload:
            payload["operationId"] = payload["id"]
        if "updates" in payload and isinstance(payload["updates"], dict):
            payload = {**payload, **payload["updates"]}

        cmd = UpdateOperationCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        op = next((o for o in clase.operations if o.id == cmd.operationId), None)
        if op is None:
            raise ElementoNoEncontrado(
                f"Operación con ID '{cmd.operationId}' no encontrada en la clase '{clase.name}'."
            )

        if cmd.name is not None:
            proposed_name = cmd.name.strip()
            param_types = tuple(p.type.strip().lower() for p in op.parameters)
            new_sig = (proposed_name.lower(), param_types)

            for other in clase.operations:
                if other.id != cmd.operationId and _compute_op_signature(other) == new_sig:
                    raise UmlValidationError(
                        f"Ya existe otra operación con la firma '{proposed_name}({', '.join(param_types)})' en la clase '{clase.name}'."
                    )
            op.name = proposed_name

        if cmd.returnType is not None:
            op.return_type = cmd.returnType.strip()

        if cmd.visibility is not None:
            op.visibility = cmd.visibility

        if cmd.isStatic is not None:
            op.is_static = cmd.isStatic

        if cmd.isAbstract is not None:
            op.is_abstract = cmd.isAbstract

        return None, None

    def _handle_delete_operation(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        if "id" in payload and "operationId" not in payload:
            payload["operationId"] = payload["id"]

        cmd = DeleteOperationCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        clase.operations = [o for o in clase.operations if o.id != cmd.operationId]
        return ElementoEliminado(elemento_id=cmd.operationId), None
