"""
Mappers entre DTOs de Pydantic y las entidades puras de core.uml_domain.
Garantiza que el dominio nunca dependa de Pydantic.
"""

import uuid

from core.uml_domain.model import (
    AggregationKind,
    AssociationEnd,
    ElementLayout,
    MultiplicityRange,
    ParameterDirectionKind,
    RelationshipLayout,
    UmlAssociation,
    UmlAttribute,
    UmlClass,
    UmlDependency,
    UmlDomainModel,
    UmlGeneralization,
    UmlOperation,
    UmlParameter,
    UmlRealization,
    UmlVisualLayout,
    ViewportLayout,
    VisibilityKind,
)

from ..schemas.uml import (
    AssociationSchema,
    AttributeSchema,
    ClassSchema,
    DependencySchema,
    GeneralizationSchema,
    MultiplicitySchema,
    OperationSchema,
    ParameterSchema,
    RealizationSchema,
    UmlModelSchema,
)


class PydanticToDomainMapper:
    """
    Convierte un DTO Pydantic validado a una entidad pura de UML Domain Model.
    """

    @classmethod
    def to_domain_model(cls, schema: UmlModelSchema) -> UmlDomainModel:
        classes: list[UmlClass] = []
        for cs in schema.classes:
            attrs: list[UmlAttribute] = []
            for a in cs.attributes:
                mult = (
                    MultiplicityRange(lower=a.multiplicity.lowerBound, upper=a.multiplicity.upperBound)
                    if a.multiplicity
                    else MultiplicityRange(1, 1)
                )
                attrs.append(
                    UmlAttribute(
                        id=a.id,
                        name=a.name,
                        type=a.type,
                        visibility=VisibilityKind.from_symbol_or_str(a.visibility),
                        default_value=a.defaultValue,
                        multiplicity=mult,
                        is_static=a.isStatic,
                        is_read_only=a.isReadOnly,
                    )
                )

            ops: list[UmlOperation] = []
            for op in cs.operations:
                params: list[UmlParameter] = []
                for p in op.parameters:
                    params.append(
                        UmlParameter(
                            id=str(uuid.uuid4()),
                            name=p.name,
                            type=p.type,
                            direction=ParameterDirectionKind(p.direction),
                            default_value=p.defaultValue,
                        )
                    )
                ops.append(
                    UmlOperation(
                        id=op.id,
                        name=op.name,
                        return_type=op.returnType,
                        visibility=VisibilityKind.from_symbol_or_str(op.visibility),
                        parameters=params,
                        is_static=op.isStatic,
                        is_abstract=op.isAbstract,
                    )
                )

            classes.append(
                UmlClass(
                    id=cs.id,
                    name=cs.name,
                    visibility=VisibilityKind.from_symbol_or_str(cs.visibility),
                    is_abstract=cs.isAbstract,
                    is_interface=cs.isInterface,
                    stereotype=cs.stereotype,
                    attributes=attrs,
                    operations=ops,
                )
            )

        associations: list[UmlAssociation] = []
        for assoc_s in schema.associations:
            end0 = assoc_s.memberEnds[0]
            end1 = assoc_s.memberEnds[1]

            m0 = MultiplicityRange(lower=end0.multiplicity.lowerBound, upper=end0.multiplicity.upperBound)
            m1 = MultiplicityRange(lower=end1.multiplicity.lowerBound, upper=end1.multiplicity.upperBound)

            dom_end0 = AssociationEnd(
                class_id=end0.classId,
                role_name=end0.roleName,
                is_navigable=end0.isNavigable,
                aggregation_kind=AggregationKind(end0.aggregationKind),
                multiplicity=m0,
            )
            dom_end1 = AssociationEnd(
                class_id=end1.classId,
                role_name=end1.roleName,
                is_navigable=end1.isNavigable,
                aggregation_kind=AggregationKind(end1.aggregationKind),
                multiplicity=m1,
            )

            associations.append(
                UmlAssociation(
                    id=assoc_s.id,
                    name=assoc_s.name,
                    member_ends=(dom_end0, dom_end1),
                )
            )

        generalizations: list[UmlGeneralization] = [
            UmlGeneralization(id=g.id, specific_class_id=g.specificClassId, general_class_id=g.generalClassId)
            for g in schema.generalizations
        ]

        realizations: list[UmlRealization] = [
            UmlRealization(id=r.id, client_class_id=r.clientClassId, supplier_interface_id=r.supplierInterfaceId)
            for r in schema.realizations
        ]

        dependencies: list[UmlDependency] = [
            UmlDependency(id=d.id, client_class_id=d.clientClassId, supplier_class_id=d.supplierClassId)
            for d in schema.dependencies
        ]

        # Layout visual si está presente
        visual_layout = None
        if schema.visualLayout:
            vl = schema.visualLayout
            vp_data = vl.get("viewport", {})
            viewport = ViewportLayout(
                zoom=float(vp_data.get("zoom", 1.0)),
                pan_x=float(vp_data.get("panX", 0.0)),
                pan_y=float(vp_data.get("panY", 0.0)),
            )
            nodes = {
                k: ElementLayout(x=float(v["x"]), y=float(v["y"]), width=float(v["width"]), height=float(v["height"]))
                for k, v in vl.get("nodes", {}).items()
            }
            links = {
                k: RelationshipLayout(vertices=v.get("vertices", []))
                for k, v in vl.get("links", {}).items()
            }
            visual_layout = UmlVisualLayout(viewport=viewport, nodes=nodes, links=links)

        return UmlDomainModel(
            schema_version=schema.schemaVersion,
            model_id=schema.modelId,
            name=schema.name,
            description=schema.description,
            classes=classes,
            associations=associations,
            generalizations=generalizations,
            realizations=realizations,
            dependencies=dependencies,
            visual_layout=visual_layout,
        )


class DomainToPydanticMapper:
    """
    Convierte una entidad de UML Domain Model pura a un DTO Pydantic para serialización HTTP.
    """

    @classmethod
    def to_pydantic_schema(cls, model: UmlDomainModel) -> UmlModelSchema:
        classes_dto: list[ClassSchema] = []
        for c in model.classes:
            attrs_dto = [
                AttributeSchema(
                    id=a.id,
                    name=a.name,
                    type=a.type,
                    visibility=a.visibility.value,
                    defaultValue=a.default_value,
                    isStatic=a.is_static,
                    isReadOnly=a.is_read_only,
                    multiplicity=MultiplicitySchema(lowerBound=a.multiplicity.lower, upperBound=a.multiplicity.upper),
                )
                for a in c.attributes
            ]
            ops_dto = [
                OperationSchema(
                    id=op.id,
                    name=op.name,
                    visibility=op.visibility.value,
                    returnType=op.return_type,
                    isStatic=op.is_static,
                    isAbstract=op.is_abstract,
                    parameters=[
                        ParameterSchema(
                            name=p.name,
                            type=p.type,
                            direction=p.direction.value,
                            defaultValue=p.default_value,
                        )
                        for p in op.parameters
                    ],
                )
                for op in c.operations
            ]
            classes_dto.append(
                ClassSchema(
                    id=c.id,
                    name=c.name,
                    visibility=c.visibility.value,
                    isAbstract=c.is_abstract,
                    isInterface=c.is_interface,
                    stereotype=c.stereotype,
                    attributes=attrs_dto,
                    operations=ops_dto,
                )
            )

        associations_dto = [
            AssociationSchema(
                id=a.id,
                name=a.name,
                memberEnds=[
                    {
                        "classId": a.member_ends[0].class_id,
                        "roleName": a.member_ends[0].role_name,
                        "isNavigable": a.member_ends[0].is_navigable,
                        "aggregationKind": a.member_ends[0].aggregation_kind.value,
                        "multiplicity": {
                            "lowerBound": a.member_ends[0].multiplicity.lower,
                            "upperBound": a.member_ends[0].multiplicity.upper,
                        },
                    },
                    {
                        "classId": a.member_ends[1].class_id,
                        "roleName": a.member_ends[1].role_name,
                        "isNavigable": a.member_ends[1].is_navigable,
                        "aggregationKind": a.member_ends[1].aggregation_kind.value,
                        "multiplicity": {
                            "lowerBound": a.member_ends[1].multiplicity.lower,
                            "upperBound": a.member_ends[1].multiplicity.upper,
                        },
                    },
                ],
            )
            for a in model.associations
        ]

        generalizations_dto = [
            GeneralizationSchema(id=g.id, specificClassId=g.specific_class_id, generalClassId=g.general_class_id)
            for g in model.generalizations
        ]

        realizations_dto = [
            RealizationSchema(id=r.id, clientClassId=r.client_class_id, supplierInterfaceId=r.supplier_interface_id)
            for r in model.realizations
        ]

        dependencies_dto = [
            DependencySchema(id=d.id, clientClassId=d.client_class_id, supplierClassId=d.supplier_class_id)
            for d in model.dependencies
        ]

        visual_layout_dict = None
        if model.visual_layout:
            vl = model.visual_layout
            visual_layout_dict = {
                "viewport": {"zoom": vl.viewport.zoom, "panX": vl.viewport.pan_x, "panY": vl.viewport.pan_y},
                "nodes": {
                    k: {"x": v.x, "y": v.y, "width": v.width, "height": v.height}
                    for k, v in vl.nodes.items()
                },
                "links": {
                    k: {"vertices": v.vertices}
                    for k, v in vl.links.items()
                },
            }

        return UmlModelSchema(
            schemaVersion=model.schema_version,
            modelId=model.model_id,
            name=model.name,
            description=model.description,
            classes=classes_dto,
            associations=associations_dto,
            generalizations=generalizations_dto,
            realizations=realizations_dto,
            dependencies=dependencies_dto,
            visualLayout=visual_layout_dict,
        )
