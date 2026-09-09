"""
Despachador centralizado de comandos para el módulo de modelado (CU3).
"""

from typing import Any

from pydantic import ValidationError

from backend_case.app.modeling.application.commands.attribute_handlers import (
    AttributeCommandHandler,
)
from backend_case.app.modeling.application.commands.base import CommandHandler
from backend_case.app.modeling.application.commands.class_handlers import (
    ClassCommandHandler,
)
from backend_case.app.modeling.application.commands.layout_handlers import (
    LayoutCommandHandler,
)
from backend_case.app.modeling.application.commands.operation_handlers import (
    OperationCommandHandler,
)
from backend_case.app.modeling.application.commands.parameter_handlers import (
    ParameterCommandHandler,
)
from backend_case.app.modeling.application.commands.relation_handlers import (
    RelationCommandHandler,
)
from core.uml_domain.events import DomainEvent
from core.uml_domain.exceptions import UmlValidationError
from core.uml_domain.model import Lienzo


class CommandDispatcher:
    """
    Registra y delega la ejecución de comandos semánticos a handlers modulares específicos.
    Elimina cualquier switch monolítico en el Application Service.
    """

    def __init__(self) -> None:
        self.handlers: list[CommandHandler] = [
            ClassCommandHandler(),
            AttributeCommandHandler(),
            OperationCommandHandler(),
            ParameterCommandHandler(),
            LayoutCommandHandler(),
            RelationCommandHandler(),
        ]

    def dispatch(
        self, lienzo: Lienzo, cmd_type: str, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        u_type = cmd_type.strip().upper()
        # Inyectar el tipo de comando en el payload para despacho interno del handler
        payload_with_type = {**payload, "__cmd_type__": u_type}

        for handler in self.handlers:
            if handler.can_handle(u_type):
                try:
                    return handler.handle(lienzo, payload_with_type)
                except ValidationError as err:
                    first_err = err.errors()[0] if err.errors() else {}
                    msg = first_err.get("msg", str(err))
                    raise UmlValidationError(msg) from err

        raise UmlValidationError(
            f"Tipo de comando '{cmd_type}' no soportado por el despachador."
        )
