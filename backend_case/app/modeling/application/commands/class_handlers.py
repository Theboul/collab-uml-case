"""
Manejadores de comandos para clases y ciclo de vida de agregados (CU1 / CU3).
"""

from typing import Any, ClassVar

from backend_case.app.application.mappers import (
    DomainToPydanticMapper,
    PydanticToDomainMapper,
)
from backend_case.app.modeling.application.commands.base import CommandHandler
from backend_case.app.modeling.application.commands.schemas import (
    CreateClassCommand,
    DeleteElementsCommand,
    ElementLayoutSchema,
    GeneralizationSchema,
    RelationSchema,
    RestoreElementsCommand,
    UpdateClassNameCommand,
)
from backend_case.app.schemas.uml import UmlModelSchema
from core.uml_domain.events import DomainEvent, ElementoAgregado, ElementoEliminado
from core.uml_domain.exceptions import ElementoNoEncontrado, UmlValidationError
from core.uml_domain.model import (
    AggregationKind,
    AssociationEnd,
    Lienzo,
    MultiplicityRange,
    UmlAssociation,
    UmlClass,
    UmlGeneralization,
)


class ClassCommandHandler(CommandHandler):
    """
    Gestiona la creación, renombrado, eliminación en cascada y restauración de clases.
    """

    SUPPORTED_COMMANDS: ClassVar[set[str]] = {
        "CREATE_CLASS",
        "ADD_CLASS",
        "UPDATE_CLASS_NAME",
        "UPDATE_CLASS",
        "DELETE_ELEMENTS",
        "DELETE_ELEMENT",
        "DELETE_CLASS",
        "RESTORE_ELEMENTS",
    }

    def can_handle(self, cmd_type: str) -> bool:
        return cmd_type.upper() in self.SUPPORTED_COMMANDS

    def handle(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, dict[str, Any] | None]:
        cmd_type = payload.get("__cmd_type__", "").upper()
        if not cmd_type:
            # Detectar por estructura o invocador
            pass

        if cmd_type in ("CREATE_CLASS", "ADD_CLASS"):
            return self._handle_create_class(lienzo, payload)
        elif cmd_type in ("UPDATE_CLASS_NAME", "UPDATE_CLASS"):
            return self._handle_update_class_name(lienzo, payload)
        elif cmd_type in ("DELETE_ELEMENTS", "DELETE_ELEMENT", "DELETE_CLASS"):
            return self._handle_delete_elements(lienzo, payload)
        elif cmd_type == "RESTORE_ELEMENTS":
            return self._handle_restore_elements(lienzo, payload)

        raise UmlValidationError(f"Comando de clase no reconocido: {cmd_type}")

    def _handle_create_class(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        # Normalizar classId si vino como 'id'
        if "id" in payload and "classId" not in payload:
            payload["classId"] = payload["id"]
        cmd = CreateClassCommand(**payload)

        # Validar unicidad de nombre de clase
        existente = lienzo.modelo.find_classifier_by_name(cmd.name)
        if existente is not None:
            raise UmlValidationError(
                f"Ya existe una clase con el nombre '{cmd.name}' en este modelo."
            )

        clase, evento = lienzo.modelo.agregar_clase(nombre=cmd.name, is_abstract=cmd.isAbstract)
        if cmd.classId:
            # Política de IDs: respetar ID propuesto por frontend si es válido y no colisiona
            if lienzo.modelo.find_classifier_by_id(cmd.classId) is not None and clase.id != cmd.classId:
                raise UmlValidationError(
                    f"El identificador '{cmd.classId}' ya se encuentra en uso."
                )
            clase.id = str(cmd.classId)

        nodes = lienzo.visual_layout.setdefault("nodes", {})
        nodes[clase.id] = {
            "x": float(cmd.x),
            "y": float(cmd.y),
            "width": float(cmd.width),
            "height": float(cmd.height),
        }
        return evento, None

    def _handle_update_class_name(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent | None, None]:
        if "id" in payload and "classId" not in payload:
            payload["classId"] = payload["id"]
        cmd = UpdateClassNameCommand(**payload)

        clase = lienzo.modelo.find_classifier_by_id(cmd.classId)
        if clase is None or not isinstance(clase, UmlClass):
            raise ElementoNoEncontrado(f"Clase con ID '{cmd.classId}' no encontrada.")

        # Comprobar unicidad ignorando mayúsculas/minúsculas con otras clases
        otro = lienzo.modelo.find_classifier_by_name(cmd.name)
        if otro is not None and otro.id != cmd.classId:
            raise UmlValidationError(
                f"Ya existe otra clase con el nombre '{cmd.name}' en este modelo."
            )

        clase.name = cmd.name.strip()
        if "isAbstract" in payload:
            clase.is_abstract = bool(payload["isAbstract"])

        return None, None

    def _handle_delete_elements(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, dict[str, Any]]:
        # Unificación: normalizar elementId / classId a classIds: list[str]
        class_ids: list[str] = []
        if "classIds" in payload and isinstance(payload["classIds"], list):
            class_ids = [str(cid) for cid in payload["classIds"] if cid]
        elif payload.get("classId"):
            class_ids = [str(payload["classId"])]
        elif payload.get("elementId"):
            class_ids = [str(payload["elementId"])]
        elif payload.get("id"):
            class_ids = [str(payload["id"])]

        cmd = DeleteElementsCommand(classIds=class_ids)
        target_ids = set(cmd.classIds)

        # 1. Capturar clases completas a eliminar
        model_dto = DomainToPydanticMapper.to_pydantic_schema(lienzo.modelo)
        deleted_classes_dto = [c for c in model_dto.classes if c.id in target_ids]

        # 2. Capturar relaciones dependientes conectadas
        deleted_relations_dto: list[RelationSchema] = []
        for assoc in list(lienzo.modelo.associations):
            if any(end.class_id in target_ids for end in assoc.member_ends):
                end1, end2 = assoc.member_ends[0], assoc.member_ends[1]
                rel_type = "ASSOCIATION"
                if end1.aggregation_kind == AggregationKind.SHARED or end2.aggregation_kind == AggregationKind.SHARED:
                    rel_type = "AGGREGATION"
                elif end1.aggregation_kind == AggregationKind.COMPOSITE or end2.aggregation_kind == AggregationKind.COMPOSITE:
                    rel_type = "COMPOSITION"

                deleted_relations_dto.append(
                    RelationSchema(
                        id=assoc.id,
                        type=rel_type,
                        sourceClassId=end1.class_id,
                        targetClassId=end2.class_id,
                        sourceMultiplicity=end1.multiplicity.to_uml_str(),
                        targetMultiplicity=end2.multiplicity.to_uml_str(),
                        sourceRole=end1.role_name,
                        targetRole=end2.role_name,
                        name=assoc.name,
                    )
                )

        deleted_gens_dto: list[GeneralizationSchema] = []
        for gen in list(lienzo.modelo.generalizations):
            if gen.specific_class_id in target_ids or gen.general_class_id in target_ids:
                deleted_gens_dto.append(
                    GeneralizationSchema(
                        id=gen.id,
                        specificClassId=gen.specific_class_id,
                        generalClassId=gen.general_class_id,
                    )
                )

        # 3. Capturar layouts de las clases
        nodes = lienzo.visual_layout.setdefault("nodes", {})
        deleted_layouts_dto: list[ElementLayoutSchema] = []
        for cid in target_ids:
            if cid in nodes:
                l_data = nodes[cid]
                deleted_layouts_dto.append(
                    ElementLayoutSchema(
                        elementId=cid,
                        x=float(l_data.get("x", 100)),
                        y=float(l_data.get("y", 100)),
                        width=float(l_data.get("width", 190)),
                        height=float(l_data.get("height", 130)),
                    )
                )

        # 4. Aplicar eliminación en cascada en ModeloUML y DiagramLayout
        lienzo.modelo.classes = [c for c in lienzo.modelo.classes if c.id not in target_ids]
        lienzo.modelo.associations = [
            a for a in lienzo.modelo.associations
            if not any(end.class_id in target_ids for end in a.member_ends)
        ]
        lienzo.modelo.generalizations = [
            g for g in lienzo.modelo.generalizations
            if g.specific_class_id not in target_ids and g.general_class_id not in target_ids
        ]
        for cid in target_ids:
            nodes.pop(cid, None)

        # 5. Construir undoPayload tipado que el backend confirma a Angular
        undo_payload = {
            "classes": [c.model_dump(mode="json") for c in deleted_classes_dto],
            "relations": [r.model_dump(mode="json") for r in deleted_relations_dto],
            "generalizations": [g.model_dump(mode="json") for g in deleted_gens_dto],
            "layouts": [l.model_dump(mode="json") for l in deleted_layouts_dto],
        }

        return ElementoEliminado(elemento_id=",".join(target_ids)), undo_payload

    def _handle_restore_elements(
        self, lienzo: Lienzo, payload: dict[str, Any]
    ) -> tuple[DomainEvent, None]:
        cmd = RestoreElementsCommand(**payload)

        # 1. Restaurar clases con sus compartimentos e IDs originales exactos
        dummy_schema = UmlModelSchema(
            modelId="restore-temp",
            name="restore",
            classes=cmd.classes,
        )
        restored_domain = PydanticToDomainMapper.to_domain_model(dummy_schema)

        existing_cids = {c.id for c in lienzo.modelo.classes}
        for restored_class in restored_domain.classes:
            if restored_class.id not in existing_cids:
                lienzo.modelo.classes.append(restored_class)

        # 2. Restaurar relaciones dependientes
        existing_rids = {a.id for a in lienzo.modelo.associations}
        for rel in cmd.relations:
            if rel.id not in existing_rids:
                end1 = AssociationEnd(
                    class_id=rel.sourceClassId,
                    role_name=rel.sourceRole,
                    multiplicity=MultiplicityRange(1, 1),
                )
                end2 = AssociationEnd(
                    class_id=rel.targetClassId,
                    role_name=rel.targetRole,
                    multiplicity=MultiplicityRange(1, 1),
                )
                if rel.type == "AGGREGATION":
                    end1.aggregation_kind = AggregationKind.SHARED
                elif rel.type == "COMPOSITION":
                    end1.aggregation_kind = AggregationKind.COMPOSITE

                lienzo.modelo.associations.append(
                    UmlAssociation(
                        id=rel.id,
                        name=rel.name,
                        member_ends=(end1, end2),
                    )
                )

        # 3. Restaurar generalizaciones
        existing_gids = {g.id for g in lienzo.modelo.generalizations}
        for gen in cmd.generalizations:
            if gen.id not in existing_gids:
                lienzo.modelo.generalizations.append(
                    UmlGeneralization(
                        id=gen.id,
                        specific_class_id=gen.specificClassId,
                        general_class_id=gen.generalClassId,
                    )
                )

        # 4. Restaurar layouts en visual_layout["nodes"]
        nodes = lienzo.visual_layout.setdefault("nodes", {})
        for l in cmd.layouts:
            nodes[l.elementId] = {
                "x": l.x,
                "y": l.y,
                "width": l.width,
                "height": l.height,
            }

        return ElementoAgregado(elemento_id="restored-aggregate", tipo="UmlAggregate"), None
