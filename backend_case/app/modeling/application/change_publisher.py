"""Puerto por el que el modelado avisa de un cambio ya confirmado (lo implementa colaboración)."""

from dataclasses import dataclass
from typing import Protocol

from backend_case.app.modeling.application.canvas_delta import CanvasDelta


@dataclass(frozen=True)
class CanvasChange:
    """Lo que cambió en un Lienzo al pasar de `from_version` a `to_version` (consecutivas)."""

    from_version: int
    to_version: int
    delta: CanvasDelta


class ChangePublisher(Protocol):
    async def canvas_changed(
        self, canvas_id: str, change: CanvasChange, origin_session_id: str = ""
    ) -> None:
        """
        Se llama DESPUÉS del commit. `origin_session_id` es la Sesión que originó el cambio ("" si
        no hay una), para no devolverle el eco.
        """
        ...
