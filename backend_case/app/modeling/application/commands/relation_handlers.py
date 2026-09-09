"""
Manejadores de comandos existentes de relaciones para retrocompatibilidad (CU1).
Nota: El ciclo de vida interactivo completo de relaciones corresponde a CU4.
"""

from typing import Any, ClassVar

from backend_case.app.modeling.application.commands.base import CommandHandler
from core.uml_domain.adapters.multiplicity_parser import LegacyMultiplicityParser
from core.uml_domain.events import DomainEvent
from core.uml_domain.exceptions import UmlValidationError
from core.uml_domain.model import (
    AggregationKind,
    Lienzo,
    MultiplicityRange,
)


class RelationCommandHandler(CommandHandler):
    """
    Gestiona comandos básicos existentes de relaciones para retrocompatibilidad.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "CREATE_RELATION",
        "ADD_RELATION",
        "ADD_ASSOCIATION",
        "UPDATE_RELATION",
        "EDIT_RELATION",
        "UPDATE_MULTIPLICITY",
        "DELETE_RELATION",
        "DELETE_ASSOCIATION",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()

        if cmd_type in ("CREATE_RELATION", "ADD_RELATION", "ADD_ASSOCIATION"):
            rel_id = payload.get("relationId") or payload.get("id")
            source_id = str(payload.get("sourceClassId") or payload.get("sourceId"))
            target_id = str(payload.get("targetClassId") or payload.get("targetId"))
            rel_type = (payload.get("type") or "ASSOCIATION").upper()
            name = payload.get("name")
            source_role = payload.get("sourceRole")
            target_role = payload.get("targetRole")
            source_mult = payload.get("sourceMultiplicity", "1")
            target_mult = payload.get("targetMultiplicity", "1")

            if rel_type == "GENERALIZATION":
                gen, evento = lienzo.modelo.agregar_generalizacion(source_id, target_id)
                if rel_id:
                    gen.id = str(rel_id)
                return evento, None
            else:
                agg_source = AggregationKind.NONE
                agg_target = AggregationKind.NONE
                if rel_type == "AGGREGATION":
                    agg_source = AggregationKind.SHARED
                elif rel_type == "COMPOSITION":
                    agg_source = AggregationKind.COMPOSITE

                m_orig = LegacyMultiplicityParser.parse(source_mult) if source_mult else MultiplicityRange(1, 1)
                m_dest = LegacyMultiplicityParser.parse(target_mult) if target_mult else MultiplicityRange(1, 1)

                asoc, evento = lienzo.modelo.agregar_asociacion(
                    origen_id=source_id,
                    destino_id=target_id,
                    nombre=name,
                    rol_origen=source_role,
                    rol_destino=target_role,
                    multiplicidad_origen=m_orig,
                    multiplicidad_destino=m_dest,
                    agregacion_origen=agg_source,
                    agregacion_destino=agg_target,
                )
                if rel_id:
                    asoc.id = str(rel_id)
                return evento, None

        elif cmd_type in ("UPDATE_RELATION", "EDIT_RELATION"):
            rel_id = str(payload.get("relationId") or payload.get("id"))
            new_type = payload.get("type")
            source_mult = payload.get("sourceMultiplicity")
            target_mult = payload.get("targetMultiplicity")

            asoc_existente = next((a for a in lienzo.modelo.associations if a.id == rel_id), None)
            if asoc_existente is None:
                return None, None

            agregacion_origen = None
            agregacion_destino = None
            if new_type:
                u_type = new_type.upper()
                if u_type == "AGGREGATION":
                    agregacion_origen, agregacion_destino = AggregationKind.SHARED, AggregationKind.NONE
                elif u_type == "COMPOSITION":
                    agregacion_origen, agregacion_destino = AggregationKind.COMPOSITE, AggregationKind.NONE
                elif u_type == "ASSOCIATION":
                    agregacion_origen, agregacion_destino = AggregationKind.NONE, AggregationKind.NONE

            _, evento = lienzo.modelo.editar_asociacion(
                rel_id,
                nombre=payload.get("name"),
                rol_origen=payload.get("sourceRole"),
                rol_destino=payload.get("targetRole"),
                multiplicidad_origen=LegacyMultiplicityParser.parse(source_mult) if source_mult is not None else None,
                multiplicidad_destino=LegacyMultiplicityParser.parse(target_mult) if target_mult is not None else None,
                agregacion_origen=agregacion_origen,
                agregacion_destino=agregacion_destino,
            )
            return evento, None

        elif cmd_type == "UPDATE_MULTIPLICITY":
            rel_id = str(payload.get("relationId") or payload.get("id"))
            asoc_existente = next((a for a in lienzo.modelo.associations if a.id == rel_id), None)
            if asoc_existente is None:
                return None, None

            src_m = payload.get("sourceMultiplicity")
            tgt_m = payload.get("targetMultiplicity")
            _, evento = lienzo.modelo.editar_asociacion(
                rel_id,
                multiplicidad_origen=LegacyMultiplicityParser.parse(src_m) if src_m else None,
                multiplicidad_destino=LegacyMultiplicityParser.parse(tgt_m) if tgt_m else None,
            )
            return evento, None

        elif cmd_type in ("DELETE_RELATION", "DELETE_ASSOCIATION"):
            rel_id = str(payload.get("relationId") or payload.get("id"))
            evento: DomainEvent | None = None
            if any(a.id == rel_id for a in lienzo.modelo.associations):
                evento = lienzo.modelo.eliminar_asociacion(rel_id)
            elif any(g.id == rel_id for g in lienzo.modelo.generalizations):
                evento = lienzo.modelo.eliminar_generalizacion(rel_id)
            links = lienzo.visual_layout.setdefault("links", {})
            links.pop(rel_id, None)
            return evento, None

        raise UmlValidationError(f"Comando de relación no reconocido: {cmd_type}")
