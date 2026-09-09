"""
Manejadores de comandos para Layout y Viewport visual (CU1).
"""

from typing import Any, ClassVar

from backend_case.app.modeling.application.commands.base import CommandHandler
from core.uml_domain.events import DomainEvent
from core.uml_domain.exceptions import UmlValidationError
from core.uml_domain.model import Lienzo


class LayoutCommandHandler(CommandHandler):
    """
    Gestiona el posicionamiento visual y viewport de AntV X6 en DiagramLayout.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "MOVE_ELEMENT",
        "MOVE_CLASS",
        "RESIZE_ELEMENT",
        "RESIZE_CLASS",
        "UPDATE_VIEWPORT",
        "UPDATE_RELATION_LAYOUT",
        "UPDATE_RELATION_VERTICES",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()

        if not isinstance(lienzo.visual_layout, dict):
            lienzo.visual_layout = {
                "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
                "nodes": {},
                "links": {},
            }

        nodes = lienzo.visual_layout.setdefault("nodes", {})

        if cmd_type in ("MOVE_ELEMENT", "MOVE_CLASS"):
            elem_id = str(payload.get("elementId") or payload.get("id") or "")
            if elem_id and elem_id in nodes:
                node = nodes[elem_id]
                node["x"] = float(payload.get("x", node.get("x", 0.0)))
                node["y"] = float(payload.get("y", node.get("y", 0.0)))
            elif elem_id:
                nodes[elem_id] = {
                    "x": float(payload.get("x", 0.0)),
                    "y": float(payload.get("y", 0.0)),
                    "width": 190.0,
                    "height": 130.0,
                }
            return None, None

        elif cmd_type in ("RESIZE_ELEMENT", "RESIZE_CLASS"):
            elem_id = str(payload.get("elementId") or payload.get("id") or "")
            if elem_id and elem_id in nodes:
                node = nodes[elem_id]
                node["width"] = max(140.0, float(payload.get("width", node.get("width", 190.0))))
                node["height"] = max(80.0, float(payload.get("height", node.get("height", 130.0))))
                if "x" in payload:
                    node["x"] = float(payload["x"])
                if "y" in payload:
                    node["y"] = float(payload["y"])
            return None, None

        elif cmd_type == "UPDATE_VIEWPORT":
            lienzo.visual_layout["viewport"] = {
                "zoom": float(payload.get("zoom", 1.0)),
                "panX": float(payload.get("panX", 0.0)),
                "panY": float(payload.get("panY", 0.0)),
            }
            return None, None

        elif cmd_type == "UPDATE_RELATION_LAYOUT":
            rel_id = str(payload.get("relationId") or payload.get("id") or "")
            if not rel_id:
                raise UmlValidationError("UPDATE_RELATION_LAYOUT requiere 'relationId'.")
            links = lienzo.visual_layout.setdefault("links", {})
            link = links.setdefault(rel_id, {})
            if payload.get("sourcePort"):
                link["sourcePort"] = str(payload["sourcePort"])
            if payload.get("targetPort"):
                link["targetPort"] = str(payload["targetPort"])
            return None, None

        elif cmd_type == "UPDATE_RELATION_VERTICES":
            rel_id = str(payload.get("relationId") or payload.get("id") or "")
            if not rel_id:
                raise UmlValidationError("UPDATE_RELATION_VERTICES requiere 'relationId'.")
            links = lienzo.visual_layout.setdefault("links", {})
            link = links.setdefault(rel_id, {})
            vertices = payload.get("vertices")
            if not isinstance(vertices, list):
                raise UmlValidationError("UPDATE_RELATION_VERTICES requiere 'vertices' (lista).")
            link["vertices"] = [
                {"x": float(v["x"]), "y": float(v["y"])} for v in vertices
            ]
            return None, None

        raise UmlValidationError(f"Comando de layout no reconocido: {cmd_type}")
