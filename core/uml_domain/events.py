"""
core/uml_domain/events.py

Eventos de dominio emitidos por el Aggregate Root (UmlDomainModel y Lienzo).
Preparados para log de cambios y coordinación en CU5 (colaboración) y CU13 (sync offline).
Cero dependencias de frameworks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class DomainEvent:
    ocurrido_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class LienzoCreado(DomainEvent):
    lienzo_id: str = ""


@dataclass(frozen=True)
class ElementoAgregado(DomainEvent):
    elemento_id: str = ""
    tipo: str = ""  # "UmlClass" | "UmlInterface" | "UmlEnumeration" | ...


@dataclass(frozen=True)
class CambioCampo:
    """Un campo que cambió: nombre del atributo de dominio (snake_case) y sus valores."""

    campo: str
    anterior: object
    nuevo: object


@dataclass(frozen=True)
class ElementoModificado(DomainEvent):
    """
    Un elemento existente cambió (clase, atributo u operación). Solo lista los campos cuyo valor
    realmente cambió, con el anterior y el nuevo: un consumidor (log de cambios, colaboración,
    undo, sync) no necesita releer el modelo para saber qué pasó.
    """

    elemento_id: str = ""
    tipo: str = ""  # "UmlClass" | "UmlAttribute" | "UmlOperation"
    contenedor_id: str = ""  # id de la clase dueña (atributos/operaciones); "" para una clase
    cambios: tuple[CambioCampo, ...] = ()


@dataclass(frozen=True)
class RelacionAgregada(DomainEvent):
    relacion_id: str = ""
    tipo: str = ""  # "UmlAssociation" | "UmlGeneralization" | "UmlRealization" | ...


@dataclass(frozen=True)
class RelacionModificada(DomainEvent):
    relacion_id: str = ""
    tipo: str = ""  # "UmlAssociation" | "UmlGeneralization" | "UmlRealization" | ...


@dataclass(frozen=True)
class RelacionEliminada(DomainEvent):
    relacion_id: str = ""
    tipo: str = ""  # "UmlAssociation" | "UmlGeneralization" | "UmlRealization" | ...


@dataclass(frozen=True)
class ElementoEliminado(DomainEvent):
    elemento_id: str = ""
