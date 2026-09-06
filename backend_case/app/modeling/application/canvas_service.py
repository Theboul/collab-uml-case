import uuid
from typing import Any

from fastapi import HTTPException, status

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
    UmlGeneralization,
)


class CanvasService:
    """
    Servicio de aplicación para la gestión de lienzos UML y sus elementos (CU1 - CU4).
    """

    def __init__(self, repository: CanvasRepository) -> None:
        self.repository = repository

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
    ) -> CanvasResult:
        """
        Ejecuta un comando del editor sobre el lienzo con validación de versión optimista.
        """
        res = await self.repository.obtener(canvas_id)
        if expected_version != res.version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "VERSION_CONFLICT",
                    "message": f"Versión esperada {expected_version} no coincide con la versión actual {res.version}.",
                    "details": [{"expectedVersion": expected_version, "currentVersion": res.version}],
                },
            )

        lienzo = res.lienzo
        if not isinstance(lienzo.visual_layout, dict):
            lienzo.visual_layout = {
                "viewport": {"zoom": 1.0, "panX": 0.0, "panY": 0.0},
                "nodes": {},
                "links": {},
            }

        nodes = lienzo.visual_layout.setdefault("nodes", {})
        links = lienzo.visual_layout.setdefault("links", {})
        cmd_upper = cmd_type.upper()

        if cmd_upper in ("CREATE_CLASS", "ADD_CLASS"):
            class_id = payload.get("classId") or payload.get("id")
            name = payload.get("name", "NuevaClase")
            is_abstract = bool(payload.get("isAbstract", False))
            clase, _ = lienzo.modelo.agregar_clase(nombre=name, is_abstract=is_abstract)
            if class_id:
                clase.id = str(class_id)
            nodes[clase.id] = {
                "x": float(payload.get("x", 100)),
                "y": float(payload.get("y", 100)),
                "width": float(payload.get("width", 180)),
                "height": float(payload.get("height", 120)),
            }

        elif cmd_upper in ("MOVE_ELEMENT", "MOVE_CLASS"):
            elem_id = payload.get("elementId") or payload.get("id")
            if elem_id and str(elem_id) in nodes:
                node = nodes[str(elem_id)]
                node["x"] = float(payload.get("x", node.get("x", 0)))
                node["y"] = float(payload.get("y", node.get("y", 0)))
            elif elem_id:
                nodes[str(elem_id)] = {
                    "x": float(payload.get("x", 0)),
                    "y": float(payload.get("y", 0)),
                    "width": 180.0,
                    "height": 120.0,
                }

        elif cmd_upper in ("RESIZE_ELEMENT", "RESIZE_CLASS"):
            elem_id = payload.get("elementId") or payload.get("id")
            if elem_id and str(elem_id) in nodes:
                node = nodes[str(elem_id)]
                node["width"] = max(140.0, float(payload.get("width", node.get("width", 180))))
                node["height"] = max(80.0, float(payload.get("height", node.get("height", 120))))
                if "x" in payload:
                    node["x"] = float(payload["x"])
                if "y" in payload:
                    node["y"] = float(payload["y"])

        elif cmd_upper in ("CREATE_RELATION", "ADD_RELATION", "ADD_ASSOCIATION"):
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
                gen = UmlGeneralization(
                    id=str(rel_id) if rel_id else str(uuid.uuid4()),
                    specific_classifier_id=source_id,
                    general_classifier_id=target_id,
                )
                lienzo.modelo.generalizations.append(gen)
            else:
                agg_source = AggregationKind.NONE
                agg_target = AggregationKind.NONE
                if rel_type == "AGGREGATION":
                    agg_source = AggregationKind.SHARED
                elif rel_type == "COMPOSITION":
                    agg_source = AggregationKind.COMPOSITE

                m_orig = LegacyMultiplicityParser.parse(source_mult) if source_mult else MultiplicityRange(1, 1)
                m_dest = LegacyMultiplicityParser.parse(target_mult) if target_mult else MultiplicityRange(1, 1)

                asoc, _ = lienzo.modelo.agregar_asociacion(
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

        elif cmd_upper in ("UPDATE_RELATION", "EDIT_RELATION"):
            rel_id = str(payload.get("relationId") or payload.get("id"))
            new_type = payload.get("type")
            source_mult = payload.get("sourceMultiplicity")
            target_mult = payload.get("targetMultiplicity")

            asoc = next((a for a in lienzo.modelo.associations if a.id == rel_id), None)
            if asoc and len(asoc.member_ends) >= 2:
                end1, end2 = asoc.member_ends[0], asoc.member_ends[1]
                if new_type:
                    u_type = new_type.upper()
                    if u_type == "AGGREGATION":
                        end1.aggregation_kind = AggregationKind.SHARED
                        end2.aggregation_kind = AggregationKind.NONE
                    elif u_type == "COMPOSITION":
                        end1.aggregation_kind = AggregationKind.COMPOSITE
                        end2.aggregation_kind = AggregationKind.NONE
                    elif u_type == "ASSOCIATION":
                        end1.aggregation_kind = AggregationKind.NONE
                        end2.aggregation_kind = AggregationKind.NONE
                if source_mult is not None:
                    end1.multiplicity = LegacyMultiplicityParser.parse(source_mult)
                if target_mult is not None:
                    end2.multiplicity = LegacyMultiplicityParser.parse(target_mult)
                if "sourceRole" in payload:
                    end1.role_name = payload["sourceRole"]
                if "targetRole" in payload:
                    end2.role_name = payload["targetRole"]
                if "name" in payload:
                    asoc.name = payload["name"]

        elif cmd_upper == "UPDATE_MULTIPLICITY":
            rel_id = str(payload.get("relationId") or payload.get("id"))
            asoc = next((a for a in lienzo.modelo.associations if a.id == rel_id), None)
            if asoc and len(asoc.member_ends) >= 2:
                if src_m := payload.get("sourceMultiplicity"):
                    asoc.member_ends[0].multiplicity = LegacyMultiplicityParser.parse(src_m)
                if tgt_m := payload.get("targetMultiplicity"):
                    asoc.member_ends[1].multiplicity = LegacyMultiplicityParser.parse(tgt_m)

        elif cmd_upper in ("DELETE_ELEMENT", "DELETE_CLASS"):
            elem_id = str(payload.get("elementId") or payload.get("id"))
            lienzo.modelo.classes = [c for c in lienzo.modelo.classes if c.id != elem_id]
            lienzo.modelo.associations = [
                a for a in lienzo.modelo.associations
                if not any(end.class_id == elem_id for end in a.member_ends)
            ]
            lienzo.modelo.generalizations = [
                g for g in lienzo.modelo.generalizations
                if g.specific_classifier_id != elem_id and g.general_classifier_id != elem_id
            ]
            nodes.pop(elem_id, None)

        elif cmd_upper in ("DELETE_RELATION", "DELETE_ASSOCIATION"):
            rel_id = str(payload.get("relationId") or payload.get("id"))
            lienzo.modelo.associations = [a for a in lienzo.modelo.associations if a.id != rel_id]
            lienzo.modelo.generalizations = [g for g in lienzo.modelo.generalizations if g.id != rel_id]
            links.pop(rel_id, None)

        elif cmd_upper == "UPDATE_VIEWPORT":
            lienzo.visual_layout["viewport"] = {
                "zoom": float(payload.get("zoom", 1.0)),
                "panX": float(payload.get("panX", 0.0)),
                "panY": float(payload.get("panY", 0.0)),
            }

        return await self.repository.guardar(lienzo)

    async def listar_lienzos(self) -> list[dict[str, Any]]:
        """
        Lista todos los lienzos registrados en la base de datos.
        """
        return await self.repository.listar()

