"""
Servicio de aplicación para el módulo de modelado (CU1 - CU4).
Opera directamente sobre el modelo de dominio puro core.uml_domain.model.
"""

from typing import Any

from backend_case.app.modeling.infrastructure.canvas_repository import CanvasRepository
from core.uml_domain.adapters.multiplicity_parser import LegacyMultiplicityParser
from core.uml_domain.events import DomainEvent
from core.uml_domain.model import (
    AggregationKind,
    Lienzo,
    MultiplicityRange,
    UmlAssociation,
    UmlClass,
)


class CanvasService:
    """
    Servicio de aplicación para la gestión de lienzos UML y sus elementos (CU1 - CU4).
    """

    def __init__(self, repository: CanvasRepository) -> None:
        self.repository = repository

    async def crear_lienzo(
        self, nombre: str = "Diagrama Sin Título", descripcion: str | None = None
    ) -> tuple[Lienzo, int, DomainEvent]:
        """
        CU1: Crear un nuevo lienzo UML persistido.
        """
        lienzo, evento = Lienzo.crear_nuevo()
        lienzo.modelo.name = nombre
        lienzo.modelo.description = descripcion
        lienzo, version = await self.repository.guardar(lienzo)
        return lienzo, version, evento

    async def obtener_lienzo(self, canvas_id: str) -> tuple[Lienzo, int]:
        """
        CU2 / CU3: Recuperar el lienzo persistido por su ID.
        """
        return await self.repository.obtener(canvas_id)

    async def agregar_clase(
        self, canvas_id: str, nombre: str, is_abstract: bool = False
    ) -> tuple[Lienzo, int, UmlClass, DomainEvent]:
        """
        CU3: Agregar una nueva clase al lienzo.
        """
        lienzo, _ = await self.repository.obtener(canvas_id)
        clase, evento = lienzo.modelo.agregar_clase(nombre=nombre, is_abstract=is_abstract)
        lienzo, version = await self.repository.guardar(lienzo)
        return lienzo, version, clase, evento

    async def agregar_asociacion(
        self,
        canvas_id: str,
        origen_id: str,
        destino_id: str,
        nombre: str | None = None,
        rol_origen: str | None = None,
        rol_destino: str | None = None,
        multiplicidad_origen: str | None = "1",
        multiplicidad_destino: str | None = "1",
        agregacion_origen: str = "none",
        agregacion_destino: str = "none",
    ) -> tuple[Lienzo, int, UmlAssociation, DomainEvent]:
        """
        CU4: Agregar una asociación binaria entre dos clases en el lienzo.
        """
        lienzo, _ = await self.repository.obtener(canvas_id)

        mult_orig = (
            LegacyMultiplicityParser.parse(multiplicidad_origen)
            if multiplicidad_origen
            else MultiplicityRange(1, 1)
        )
        mult_dest = (
            LegacyMultiplicityParser.parse(multiplicidad_destino)
            if multiplicidad_destino
            else MultiplicityRange(1, 1)
        )

        agg_orig = AggregationKind(agregacion_origen.lower()) if agregacion_origen else AggregationKind.NONE
        agg_dest = AggregationKind(agregacion_destino.lower()) if agregacion_destino else AggregationKind.NONE

        asociacion, evento = lienzo.modelo.agregar_asociacion(
            origen_id=origen_id,
            destino_id=destino_id,
            nombre=nombre,
            rol_origen=rol_origen,
            rol_destino=rol_destino,
            multiplicidad_origen=mult_orig,
            multiplicidad_destino=mult_dest,
            agregacion_origen=agg_orig,
            agregacion_destino=agg_dest,
        )

        lienzo, version = await self.repository.guardar(lienzo)
        return lienzo, version, asociacion, evento

    async def listar_lienzos(self) -> list[dict[str, Any]]:
        """
        Lista todos los lienzos registrados en la base de datos.
        """
        return await self.repository.listar()
