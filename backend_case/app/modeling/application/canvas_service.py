from typing import Any

from fastapi import HTTPException, status

from backend_case.app.modeling.application.commands.dispatcher import (
    CommandDispatcher,
)
from backend_case.app.modeling.infrastructure.canvas_repository import (
    CanvasRepository,
    CanvasResult,
)
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
        self.command_dispatcher = CommandDispatcher()

    async def crear_lienzo(
        self,
        nombre: str = "Diagrama Sin Título",
        descripcion: str | None = None,
        owner_id: str | None = None,
        room_name: str | None = None,
    ) -> CanvasResult:
        """
        CU1: Crear un nuevo lienzo UML persistido de manera atómica con su usuario anfitrión.
        """
        lienzo, _ = Lienzo.crear_nuevo()
        lienzo.modelo.name = nombre
        lienzo.modelo.description = descripcion
        lienzo.visual_layout = {
            "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
            "nodes": {},
            "links": {},
        }
        return await self.repository.guardar(
            lienzo=lienzo,
            owner_id=owner_id,
            room_name=room_name,
        )

    async def obtener_lienzo(self, canvas_id: str, user_id: str | None = None) -> CanvasResult:
        """
        CU2 / CU3: Recuperar el lienzo persistido por su ID y resolver el rol del usuario.
        """
        res = await self.repository.obtener(canvas_id)
        role = await self.repository.resolver_rol(canvas_id, res.owner_id, user_id)
        return CanvasResult(
            lienzo=res.lienzo,
            version=res.version,
            owner_id=res.owner_id,
            room_name=res.room_name,
            role=role,
        )

    async def obtener_por_room_name(self, room_name: str, user_id: str | None = None) -> CanvasResult:
        """
        Recuperar el lienzo a través del código o mecanismo de acceso de sala y resolver rol.
        """
        res = await self.repository.obtener_por_room_name(room_name)
        role = await self.repository.resolver_rol(res.lienzo.id, res.owner_id, user_id)
        return CanvasResult(
            lienzo=res.lienzo,
            version=res.version,
            owner_id=res.owner_id,
            room_name=res.room_name,
            role=role,
        )

    async def unirse_a_lienzo(self, access_code: str, user_id: str) -> dict[str, Any]:
        """
        CU2: Unirse a un lienzo UML existente mediante código o enlace.
        - Valida el código de acceso normalizándolo.
        - Preserva el rol ANFITRION si es el owner del lienzo.
        - Registra la participación de forma idempotente como COLABORADOR.
        """
        canvas = await self.repository.buscar_por_codigo_acceso(access_code)
        if canvas is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "ACCESS_CODE_INVALID",
                    "message": f"El código de acceso '{access_code}' no corresponde a ningún lienzo activo.",
                },
            )

        if canvas.owner_id and canvas.owner_id == user_id:
            return {
                "workspaceId": canvas.id,
                "canvasId": canvas.id,
                "roomName": canvas.room_name,
                "role": "ANFITRION",
                "joined": False,
            }

        ya_colaborador = await self.repository.es_colaborador(canvas.id, user_id)
        if ya_colaborador:
            return {
                "workspaceId": canvas.id,
                "canvasId": canvas.id,
                "roomName": canvas.room_name,
                "role": "COLABORADOR",
                "joined": False,
            }

        await self.repository.agregar_colaborador(canvas.id, user_id)
        return {
            "workspaceId": canvas.id,
            "canvasId": canvas.id,
            "roomName": canvas.room_name,
            "role": "COLABORADOR",
            "joined": True,
        }


    async def agregar_clase(
        self, canvas_id: str, nombre: str, is_abstract: bool = False
    ) -> tuple[Lienzo, int, UmlClass, DomainEvent]:
        """
        CU3: Agregar una nueva clase al lienzo.
        """
        res = await self.repository.obtener(canvas_id)
        lienzo = res.lienzo
        clase, evento = lienzo.modelo.agregar_clase(nombre=nombre, is_abstract=is_abstract)
        saved = await self.repository.guardar(lienzo)
        return saved.lienzo, saved.version, clase, evento

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
        res = await self.repository.obtener(canvas_id)
        lienzo = res.lienzo

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

        saved = await self.repository.guardar(lienzo)
        return saved.lienzo, saved.version, asociacion, evento

    async def ejecutar_comando(
        self,
        canvas_id: str,
        operation_id: str,
        expected_version: int,
        cmd_type: str,
        payload: dict[str, Any],
    ) -> tuple[CanvasResult, dict[str, Any] | None]:
        """
        Ejecuta un comando del editor sobre el lienzo delegándolo al despachador modular
        y persistiendo el cambio de manera atómica con verificación optimista de versión.
        """
        res = await self.repository.obtener(canvas_id)
        if not isinstance(res.lienzo.visual_layout, dict):
            res.lienzo.visual_layout = {
                "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
                "nodes": {},
                "links": {},
            }

        # Despachar comando semántico al handler correspondiente
        _, undo_payload = self.command_dispatcher.dispatch(res.lienzo, cmd_type, payload)

        # Persistir de forma atómica validando que la versión siga siendo expected_version
        saved_result = await self.repository.guardar_atomico(
            canvas_id=canvas_id,
            expected_version=expected_version,
            lienzo=res.lienzo,
        )

        return saved_result, undo_payload

    async def listar_lienzos(self) -> list[dict[str, Any]]:
        """
        Lista todos los lienzos registrados en la base de datos.
        """
        return await self.repository.listar()

