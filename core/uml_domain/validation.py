"""
Motor de Validación Semántica UML 2.5 y Perfiles de Compatibilidad.

Este módulo separa estrictamente la Validación Semántica UML 2.5 pura
de los Perfiles de Compatibilidad de Generación (Spring Boot y Flutter).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict

from .model import AggregationKind, UmlDomainModel


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    element_id: str | None = None
    element_type: str | None = None
    related_ids: list[str] = field(default_factory=list)
    suggestion: str | None = None


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    @property
    def infos(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.INFO]


@dataclass
class ValidationContext:
    """
    Estado compartido entre reglas dentro de una misma corrida de `validate()`.
    El orden de ejecución en `UMLValidator.RULES` importa: las reglas que
    construyen datos que otras necesitan (ej. `classifier_ids`) deben correr
    antes que las que los consumen — no son reglas 100% independientes entre
    sí, son un pipeline ordenado con contexto compartido explícito.
    """

    seen_ids: dict[str, str] = field(default_factory=dict)
    classifier_ids: set[str] = field(default_factory=set)


def _check_id(ctx: ValidationContext, elem_id: str, kind: str) -> list[ValidationIssue]:
    """
    Verifica que `elem_id` exista y no esté duplicado en todo el modelo,
    registrándolo en `ctx.seen_ids` — compartido por todas las reglas que lo
    invocan, en el mismo orden que antes del refactor a pipeline, para que
    el mensaje "ya usado en X" siga dependiendo del mismo orden de recorrido.
    """
    if not elem_id:
        return [
            ValidationIssue(
                code="VUML-02",
                message=f"Elemento de tipo '{kind}' carece de identificador estable (ID).",
                severity=ValidationSeverity.ERROR,
                element_type=kind,
            )
        ]
    if elem_id in ctx.seen_ids:
        return [
            ValidationIssue(
                code="VUML-02",
                message=(
                    f"Identificador duplicado '{elem_id}' en '{kind}' "
                    f"(ya usado en '{ctx.seen_ids[elem_id]}')."
                ),
                severity=ValidationSeverity.ERROR,
                element_id=elem_id,
                element_type=kind,
            )
        ]
    ctx.seen_ids[elem_id] = kind
    return []


def _rule_model_metadata(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-01 (schema_version), VUML-03 (nombre del modelo)."""
    issues: list[ValidationIssue] = []
    if not model.schema_version:
        issues.append(
            ValidationIssue(
                code="VUML-01",
                message="El modelo debe especificar 'schema_version'.",
                severity=ValidationSeverity.ERROR,
                element_type="UmlDomainModel",
            )
        )
    if not model.name or not model.name.strip():
        issues.append(
            ValidationIssue(
                code="VUML-03",
                message="El nombre del modelo no puede estar vacío.",
                severity=ValidationSeverity.ERROR,
                element_type="UmlDomainModel",
            )
        )
    return issues


def _rule_classifiers(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-02 (IDs), VUML-03 (nombre vacío/duplicado). Puebla `ctx.classifier_ids`."""
    issues: list[ValidationIssue] = []
    all_classifiers = model.classes + model.interfaces + model.enumerations + model.data_types
    classifier_names: set[str] = set()

    for c in all_classifiers:
        kind = type(c).__name__
        issues.extend(_check_id(ctx, c.id, kind))
        ctx.classifier_ids.add(c.id)

        if not c.name or not c.name.strip():
            issues.append(
                ValidationIssue(
                    code="VUML-03",
                    message=f"Clasificador con ID '{c.id}' tiene nombre vacío.",
                    severity=ValidationSeverity.ERROR,
                    element_id=c.id,
                    element_type=kind,
                )
            )
        else:
            name_norm = c.name.strip().lower()
            if name_norm in classifier_names:
                issues.append(
                    ValidationIssue(
                        code="VUML-03",
                        message=f"Nombre de clasificador duplicado: '{c.name}'.",
                        severity=ValidationSeverity.ERROR,
                        element_id=c.id,
                        element_type=kind,
                        suggestion=(
                            f"Renombrá '{c.name}' o el otro clasificador que usa el mismo nombre."
                        ),
                    )
                )
            classifier_names.add(name_norm)

    return issues


def _rule_attributes_and_operations(
    model: UmlDomainModel, ctx: ValidationContext
) -> list[ValidationIssue]:
    """VUML-02 (IDs de atributos/operaciones/parámetros), VUML-04 (atributos), VUML-05 (firmas)."""
    issues: list[ValidationIssue] = []

    for c in model.classes:
        attr_names: set[str] = set()
        for attr in c.attributes:
            issues.extend(_check_id(ctx, attr.id, "UmlAttribute"))
            if not attr.name or not attr.name.strip():
                issues.append(
                    ValidationIssue(
                        code="VUML-04",
                        message=f"Atributo en clase '{c.name}' no tiene nombre.",
                        severity=ValidationSeverity.ERROR,
                        element_id=attr.id,
                        element_type="UmlAttribute",
                        related_ids=[c.id],
                    )
                )
            else:
                attr_norm = attr.name.strip().lower()
                if attr_norm in attr_names:
                    issues.append(
                        ValidationIssue(
                            code="VUML-04",
                            message=f"Atributo duplicado '{attr.name}' en la clase '{c.name}'.",
                            severity=ValidationSeverity.ERROR,
                            element_id=attr.id,
                            element_type="UmlAttribute",
                            related_ids=[c.id],
                            suggestion=(
                                f"Renombrá uno de los atributos '{attr.name}' "
                                f"en la clase '{c.name}'."
                            ),
                        )
                    )
                attr_names.add(attr_norm)

        method_signatures: set[str] = set()
        for op in c.operations:
            issues.extend(_check_id(ctx, op.id, "UmlOperation"))
            for p in op.parameters:
                issues.extend(_check_id(ctx, p.id, "UmlParameter"))

            param_types = ",".join(p.type.strip().lower() for p in op.parameters)
            sig = f"{op.name.strip().lower()}({param_types})"
            if sig in method_signatures:
                issues.append(
                    ValidationIssue(
                        code="VUML-05",
                        message=f"Firma de método duplicada '{op.name}' en la clase '{c.name}'.",
                        severity=ValidationSeverity.ERROR,
                        element_id=op.id,
                        element_type="UmlOperation",
                        related_ids=[c.id],
                        suggestion=(
                            f"Cambiá el nombre o los parámetros de uno de los métodos '{op.name}'."
                        ),
                    )
                )
            method_signatures.add(sig)

    return issues


def _rule_generalizations(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-02 (IDs), VUML-06 (endpoints/auto-herencia), VUML-07 (ciclos, DFS)."""
    issues: list[ValidationIssue] = []
    inheritance_graph: dict[str, list[str]] = {cid: [] for cid in ctx.classifier_ids}

    for gen in model.generalizations:
        issues.extend(_check_id(ctx, gen.id, "UmlGeneralization"))

        if gen.specific_class_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-06",
                    message=f"Subclase '{gen.specific_class_id}' en generalización no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=gen.id,
                    element_type="UmlGeneralization",
                    related_ids=[gen.specific_class_id, gen.general_class_id],
                )
            )
        if gen.general_class_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-06",
                    message=f"Superclase '{gen.general_class_id}' en generalización no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=gen.id,
                    element_type="UmlGeneralization",
                    related_ids=[gen.specific_class_id, gen.general_class_id],
                )
            )

        if gen.specific_class_id == gen.general_class_id:
            issues.append(
                ValidationIssue(
                    code="VUML-06",
                    message=f"Una clase no puede heredar de sí misma (ID '{gen.specific_class_id}').",
                    severity=ValidationSeverity.ERROR,
                    element_id=gen.id,
                    element_type="UmlGeneralization",
                    related_ids=[gen.specific_class_id],
                    suggestion="Quitá la relación de herencia hacia sí misma.",
                )
            )

        if (
            gen.specific_class_id in inheritance_graph
            and gen.general_class_id in ctx.classifier_ids
        ):
            inheritance_graph[gen.specific_class_id].append(gen.general_class_id)

    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

    def has_cycle(node: str, path: list[str]) -> bool:
        visited[node] = 1
        for neighbor in inheritance_graph.get(node, []):
            if visited.get(neighbor, 0) == 1:
                full_cycle_ids = [*path, neighbor]
                cycle_path = " -> ".join(full_cycle_ids)
                issues.append(
                    ValidationIssue(
                        code="VUML-07",
                        message=f"Ciclo de herencia detectado (DAG violado): {cycle_path}.",
                        severity=ValidationSeverity.ERROR,
                        element_id=node,
                        element_type="UmlClass",
                        related_ids=full_cycle_ids,
                        suggestion=(
                            "Quitá una de las relaciones de generalización del ciclo "
                            "para restaurar un DAG válido."
                        ),
                    )
                )
                return True
            if visited.get(neighbor, 0) == 0 and has_cycle(neighbor, [*path, neighbor]):
                return True
        visited[node] = 2
        return False

    for cid in ctx.classifier_ids:
        if visited.get(cid, 0) == 0:
            has_cycle(cid, [cid])

    return issues


def _rule_realizations(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-02 (IDs), VUML-09 (endpoints y que el proveedor sea una interfaz formal)."""
    issues: list[ValidationIssue] = []
    interface_ids = {i.id for i in model.interfaces}
    for c in model.classes:
        if c.is_interface:
            interface_ids.add(c.id)

    for real in model.realizations:
        issues.extend(_check_id(ctx, real.id, "UmlRealization"))
        if real.client_class_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-09",
                    message=f"Clase cliente '{real.client_class_id}' en realización no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=real.id,
                    element_type="UmlRealization",
                    related_ids=[real.client_class_id, real.supplier_interface_id],
                )
            )
        if real.supplier_interface_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-09",
                    message=f"Interfaz proveedora '{real.supplier_interface_id}' en realización no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=real.id,
                    element_type="UmlRealization",
                    related_ids=[real.client_class_id, real.supplier_interface_id],
                )
            )
        elif real.supplier_interface_id not in interface_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-09",
                    message=(
                        f"El elemento proveedor '{real.supplier_interface_id}' en realización "
                        "no es una interfaz formal (is_interface=True o UmlInterface)."
                    ),
                    severity=ValidationSeverity.ERROR,
                    element_id=real.id,
                    element_type="UmlRealization",
                    related_ids=[real.client_class_id, real.supplier_interface_id],
                    suggestion=(
                        "Apuntá la realización a una interfaz formal, o marcá "
                        "is_interface=True en la clase proveedora."
                    ),
                )
            )

    return issues


def _rule_dependencies(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-02 (IDs), VUML-10 (endpoints)."""
    issues: list[ValidationIssue] = []
    for dep in model.dependencies:
        issues.extend(_check_id(ctx, dep.id, "UmlDependency"))
        if dep.client_class_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-10",
                    message=f"Clase cliente '{dep.client_class_id}' en dependencia no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=dep.id,
                    element_type="UmlDependency",
                    related_ids=[dep.client_class_id, dep.supplier_class_id],
                )
            )
        if dep.supplier_class_id not in ctx.classifier_ids:
            issues.append(
                ValidationIssue(
                    code="VUML-10",
                    message=f"Clase proveedora '{dep.supplier_class_id}' en dependencia no existe.",
                    severity=ValidationSeverity.ERROR,
                    element_id=dep.id,
                    element_type="UmlDependency",
                    related_ids=[dep.client_class_id, dep.supplier_class_id],
                )
            )
    return issues


def _rule_associations(model: UmlDomainModel, ctx: ValidationContext) -> list[ValidationIssue]:
    """VUML-02 (IDs), VUML-11 (endpoints), VUML-12 (multiplicidad de composición)."""
    issues: list[ValidationIssue] = []

    for assoc in model.associations:
        issues.extend(_check_id(ctx, assoc.id, "UmlAssociation"))
        end_a, end_b = assoc.member_ends

        for idx, end in enumerate([end_a, end_b]):
            if end.class_id not in ctx.classifier_ids:
                issues.append(
                    ValidationIssue(
                        code="VUML-11",
                        message=f"Extremo de asociación {idx} apunta a una clase inexistente ('{end.class_id}').",
                        severity=ValidationSeverity.ERROR,
                        element_id=assoc.id,
                        element_type="UmlAssociation",
                        related_ids=[end_a.class_id, end_b.class_id],
                        suggestion="Verificá que ambos extremos apunten a clases existentes.",
                    )
                )

        if (
            end_a.aggregation_kind == AggregationKind.COMPOSITE
            and end_a.multiplicity.upper is not None
            and end_a.multiplicity.upper > 1
        ):
            issues.append(
                ValidationIssue(
                    code="VUML-12",
                    message="En una composición, la multiplicidad del extremo compuesto no puede superar 1.",
                    severity=ValidationSeverity.ERROR,
                    element_id=assoc.id,
                    element_type="UmlAssociation",
                    related_ids=[end_a.class_id, end_b.class_id],
                    suggestion="Cambiá la multiplicidad del extremo compuesto a 0..1 o 1.",
                )
            )
        if (
            end_b.aggregation_kind == AggregationKind.COMPOSITE
            and end_b.multiplicity.upper is not None
            and end_b.multiplicity.upper > 1
        ):
            issues.append(
                ValidationIssue(
                    code="VUML-12",
                    message="En una composición, la multiplicidad del extremo compuesto no puede superar 1.",
                    severity=ValidationSeverity.ERROR,
                    element_id=assoc.id,
                    element_type="UmlAssociation",
                    related_ids=[end_a.class_id, end_b.class_id],
                    suggestion="Cambiá la multiplicidad del extremo compuesto a 0..1 o 1.",
                )
            )

    return issues


RuleFn = Callable[[UmlDomainModel, ValidationContext], list[ValidationIssue]]


class UMLValidator:
    """
    Validador semántico puro de diagramas de clases UML 2.5.
    Agnóstico de cualquier lenguaje o generador de código de destino.

    Fase 2 (CU9): refactor de un único método monolítico a un pipeline
    ordenado de funciones de regla — cada una `(model, ctx) -> issues`, sin
    mutar el modelo ni tener side-effects fuera de `ValidationContext`. El
    orden en `RULES` importa: las reglas que construyen datos que otras
    necesitan (ej. `classifier_ids`) corren antes que las que los consumen.
    Agregar una regla nueva es escribir la función y sumarla a esta lista,
    sin tocar un switch gigante ni las reglas existentes.
    """

    RULES: ClassVar[list[RuleFn]] = [
        _rule_model_metadata,
        _rule_classifiers,
        _rule_attributes_and_operations,
        _rule_generalizations,
        _rule_realizations,
        _rule_dependencies,
        _rule_associations,
    ]

    def validate(self, model: UmlDomainModel) -> ValidationResult:
        ctx = ValidationContext()
        issues: list[ValidationIssue] = []
        for rule in self.RULES:
            issues.extend(rule(model, ctx))
        return ValidationResult(issues=issues)


class SpringCompatibilityValidator:
    """
    Validador de compatibilidad específico para el generador legacy Spring Boot 3.5.5.
    """

    def validate_compatibility(self, model: UmlDomainModel) -> ValidationResult:
        result = ValidationResult()

        # 1. Comprobar herencia simple (Java no admite herencia múltiple de clases concretas)
        subclass_gen_count: Dict[str, int] = {}
        for gen in model.generalizations:
            subclass_gen_count[gen.specific_class_id] = subclass_gen_count.get(gen.specific_class_id, 0) + 1
            if subclass_gen_count[gen.specific_class_id] > 1:
                cls_name = getattr(model.find_classifier_by_id(gen.specific_class_id), "name", gen.specific_class_id)
                result.issues.append(
                    ValidationIssue(
                        code="VGEN-SB-01",
                        message=(
                            f"La clase '{cls_name}' posee múltiples relaciones de generalización. "
                            "Incompatible con generación de entidades Java estándar."
                        ),
                        severity=ValidationSeverity.ERROR,
                        element_id=gen.specific_class_id,
                    )
                )

        # 2. Advertencia sobre Interfaces (las plantillas v1 de Spring Boot no las generan)
        if model.interfaces or model.realizations:
            result.issues.append(
                ValidationIssue(
                    code="VGEN-SB-03",
                    message="El generador Spring Boot v1 no genera código para interfaces o relaciones de realización.",
                    severity=ValidationSeverity.WARNING,
                )
            )

        return result


class FlutterCompatibilityValidator:
    """
    Validador de compatibilidad específico para el generador legacy Flutter CRUD.
    """

    def validate_compatibility(self, model: UmlDomainModel) -> ValidationResult:
        result = ValidationResult()

        # 1. Clases abstractas no generan pantalla de captura directa
        for c in model.classes:
            if c.is_abstract:
                result.issues.append(
                    ValidationIssue(
                        code="VGEN-FL-01",
                        message=f"La clase abstracta '{c.name}' no tendrá pantalla de formulario CRUD directa.",
                        severity=ValidationSeverity.WARNING,
                        element_id=c.id,
                    )
                )

        return result
