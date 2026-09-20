"""Puerto por el que el modelado avisa de un cambio ya confirmado (lo implementa colaboración)."""

from typing import Protocol

from backend_case.app.modeling.infrastructure.canvas_repository import CanvasResult


class ChangePublisher(Protocol):
    async def canvas_changed(
        self, canvas_id: str, result: CanvasResult, origin_session_id: str = ""
    ) -> None:
        """
        Se llama DESPUÉS del commit. `origin_session_id` es la Sesión que originó el cambio ("" si
        no hay una), para no devolverle el eco.
        """
        ...
