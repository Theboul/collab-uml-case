"""
Protocolo base para manejadores de comandos semánticos (CU3).
"""

from typing import Any, Protocol

from core.uml_domain.events import DomainEvent
from core.uml_domain.model import Lienzo


class CommandHandler(Protocol):
    def can_handle(self, cmd_type: str) -> bool:
        """Indica si el handler procesa este tipo de comando."""
        ...

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        """
        Ejecuta la mutación semántica pura sobre el agregado Lienzo / ModeloUML.
        Retorna (DomainEvent opcional, undo_payload opcional).
        """
        ...
