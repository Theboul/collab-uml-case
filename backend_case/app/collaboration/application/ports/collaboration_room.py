"""
Puerto de la Sala de colaboración (ADR-0003 y su Addendum).

Una Sala agrupa las Sesiones (conexiones) de un Lienzo. El puerto es deliberadamente pequeño:
quien lo usa no sabe cómo se guardan las Sesiones, cómo se retiran las que murieron ni si hay un
solo proceso o varios detrás. Los locks y la presencia se añaden aquí cuando se implementen.
"""

from dataclasses import dataclass
from typing import Any, Protocol


class Connection(Protocol):
    """Lo único que la Sala necesita de una conexión: poder enviarle texto."""

    async def send_text(self, data: str) -> None: ...


@dataclass(frozen=True)
class Session:
    """Handle de una conexión dentro de una Sala."""

    id: str
    display_name: str | None = None
    user_id: str | None = None


class CollaborationRoom(Protocol):
    async def join(
        self,
        canvas_id: str,
        connection: Connection,
        display_name: str | None = None,
        user_id: str | None = None,
    ) -> Session:
        """Registra la conexión en la Sala del Lienzo y devuelve su Sesión."""
        ...

    async def leave(self, canvas_id: str, session: Session) -> None:
        """Retira la Sesión. Es seguro llamarlo más de una vez o con una Sesión ya retirada."""
        ...

    async def members(self, canvas_id: str) -> list[Session]:
        """Lista las Sesiones activas en la Sala del Lienzo."""
        ...

    async def publish(
        self,
        canvas_id: str,
        sender_session_id: str,
        payload: Any,
        exclude_sender: bool = True,
    ) -> None:
        """
        Envía `payload` a las Sesiones de la Sala. Cada una recibe el texto JSON:
        `{"from": <emisor>, "fromDisplayName": <nombre|null>, "payload": <payload>}`.
        Si `exclude_sender=True` (por defecto), se omite la del emisor. Si es False, llega a todas.
        `sender_session_id` puede ser "" (cambio HTTP sin Sesión de origen): llega a todas.
        Una Sesión a la que no se puede enviar se da por desconectada y se retira.
        """
        ...
