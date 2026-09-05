"""
Motor de Validación Semántica UML 2.5 y Perfiles de Compatibilidad.

Este módulo separa estrictamente la Validación Semántica UML 2.5 pura
de los Perfiles de Compatibilidad de Generación (Spring Boot y Flutter).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set
import re

from .model import (
    UmlDomainModel,
    UmlClass,
    UmlInterface,
    AggregationKind,
)


class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: ValidationSeverity = ValidationSeverity.ERROR
    element_id: Optional[str] = None


@dataclass
class ValidationResult:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == ValidationSeverity.ERROR for i in self.issues)

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class UMLValidator:
    """
    Validador semántico puro de diagramas de clases UML 2.5.
    Agnóstico de cualquier lenguaje o generador de código de destino.
    """

    def validate(self, model: UmlDomainModel) -> ValidationResult:
        result = ValidationResult()

        # 1. Validación de versión y metadatos básicos
        if not model.schema_version:
            result.issues.append(
                ValidationIssue(
                    code="VUML-01",
                    message="El modelo debe especificar 'schema_version'.",
                    severity=ValidationSeverity.ERROR,
                )
            )

        if not model.name or not model.name.strip():
            result.issues.append(
                ValidationIssue(
                    code="VUML-03",
                    message="El nombre del modelo no puede estar vacío.",
                    severity=ValidationSeverity.ERROR,
                )
            )

        # 2. Unicidad de Identificadores (UUIDs)
        seen_ids: Dict[str, str] = {}  # id -> tipo_elemento

        def check_id(elem_id: str, kind: str):
            if not elem_id:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-02",
                        message=f"Elemento de tipo '{kind}' carece de identificador estable (ID).",
                        severity=ValidationSeverity.ERROR,
                    )
                )
                return
            if elem_id in seen_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-02",
                        message=f"Identificador duplicado '{elem_id}' en '{kind}' (ya usado en '{seen_ids[elem_id]}').",
                        severity=ValidationSeverity.ERROR,
                        element_id=elem_id,
                    )
                )
            else:
                seen_ids[elem_id] = kind

        all_classifiers = model.classes + model.interfaces + model.enumerations + model.data_types
        classifier_ids: Set[str] = set()
        classifier_names: Set[str] = set()

        for c in all_classifiers:
            check_id(c.id, type(c).__name__)
            classifier_ids.add(c.id)

            # Validar nombre del clasificador
            if not c.name or not c.name.strip():
                result.issues.append(
                    ValidationIssue(
                        code="VUML-03",
                        message=f"Clasificador con ID '{c.id}' tiene nombre vacío.",
                        severity=ValidationSeverity.ERROR,
                        element_id=c.id,
                    )
                )
            else:
                name_norm = c.name.strip().lower()
                if name_norm in classifier_names:
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-03",
                            message=f"Nombre de clasificador duplicado: '{c.name}'.",
                            severity=ValidationSeverity.ERROR,
                            element_id=c.id,
                        )
                    )
                classifier_names.add(name_norm)

        # 3. Validar atributos y métodos de clases
        for c in model.classes:
            attr_names: Set[str] = set()
            for attr in c.attributes:
                check_id(attr.id, "UmlAttribute")
                if not attr.name or not attr.name.strip():
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-04",
                            message=f"Atributo en clase '{c.name}' no tiene nombre.",
                            severity=ValidationSeverity.ERROR,
                            element_id=attr.id,
                        )
                    )
                else:
                    attr_norm = attr.name.strip().lower()
                    if attr_norm in attr_names:
                        result.issues.append(
                            ValidationIssue(
                                code="VUML-04",
                                message=f"Atributo duplicado '{attr.name}' en la clase '{c.name}'.",
                                severity=ValidationSeverity.ERROR,
                                element_id=attr.id,
                            )
                        )
                    attr_names.add(attr_norm)

            method_signatures: Set[str] = set()
            for op in c.operations:
                check_id(op.id, "UmlOperation")
                for p in op.parameters:
                    check_id(p.id, "UmlParameter")

                param_types = ",".join(p.type.strip().lower() for p in op.parameters)
                sig = f"{op.name.strip().lower()}({param_types})"
                if sig in method_signatures:
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-05",
                            message=f"Firma de método duplicada '{op.name}' en la clase '{c.name}'.",
                            severity=ValidationSeverity.ERROR,
                            element_id=op.id,
                        )
                    )
                method_signatures.add(sig)

        # 4. Validar Generalizaciones (Herencia)
        inheritance_graph: Dict[str, List[str]] = {cid: [] for cid in classifier_ids}

        for gen in model.generalizations:
            check_id(gen.id, "UmlGeneralization")

            # Existencia de extremos
            if gen.specific_class_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-06",
                        message=f"Subclase '{gen.specific_class_id}' en generalización no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=gen.id,
                    )
                )
            if gen.general_class_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-06",
                        message=f"Superclase '{gen.general_class_id}' en generalización no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=gen.id,
                    )
                )

            # Auto-herencia
            if gen.specific_class_id == gen.general_class_id:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-06",
                        message=f"Una clase no puede heredar de sí misma (ID '{gen.specific_class_id}').",
                        severity=ValidationSeverity.ERROR,
                        element_id=gen.id,
                    )
                )

            if (
                gen.specific_class_id in inheritance_graph
                and gen.general_class_id in classifier_ids
            ):
                inheritance_graph[gen.specific_class_id].append(gen.general_class_id)

        # Detección de ciclos de herencia (DAG check con DFS)
        visited: Dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited

        def has_cycle(node: str, path: List[str]) -> bool:
            visited[node] = 1
            for neighbor in inheritance_graph.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    cycle_path = " -> ".join(path + [neighbor])
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-07",
                            message=f"Ciclo de herencia detectado (DAG violado): {cycle_path}.",
                            severity=ValidationSeverity.ERROR,
                            element_id=node,
                        )
                    )
                    return True
                if visited.get(neighbor, 0) == 0:
                    if has_cycle(neighbor, path + [neighbor]):
                        return True
            visited[node] = 2
            return False

        for cid in classifier_ids:
            if visited.get(cid, 0) == 0:
                has_cycle(cid, [cid])

        # 5. Validar Realizaciones (Implementación de interfaces)
        interface_ids = {i.id for i in model.interfaces}
        for c in model.classes:
            if c.is_interface:
                interface_ids.add(c.id)

        for real in model.realizations:
            check_id(real.id, "UmlRealization")
            if real.client_class_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-09",
                        message=f"Clase cliente '{real.client_class_id}' en realización no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=real.id,
                    )
                )
            if real.supplier_interface_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-09",
                        message=f"Interfaz proveedora '{real.supplier_interface_id}' en realización no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=real.id,
                    )
                )
            elif real.supplier_interface_id not in interface_ids:
                # El proveedor no es una interfaz
                result.issues.append(
                    ValidationIssue(
                        code="VUML-09",
                        message=(
                            f"El elemento proveedor '{real.supplier_interface_id}' en realización "
                            "no es una interfaz formal (is_interface=True o UmlInterface)."
                        ),
                        severity=ValidationSeverity.ERROR,
                        element_id=real.id,
                    )
                )

        # 6. Validar Dependencias
        for dep in model.dependencies:
            check_id(dep.id, "UmlDependency")
            if dep.client_class_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-10",
                        message=f"Clase cliente '{dep.client_class_id}' en dependencia no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=dep.id,
                    )
                )
            if dep.supplier_class_id not in classifier_ids:
                result.issues.append(
                    ValidationIssue(
                        code="VUML-10",
                        message=f"Clase proveedora '{dep.supplier_class_id}' en dependencia no existe.",
                        severity=ValidationSeverity.ERROR,
                        element_id=dep.id,
                    )
                )

        # 7. Validar Asociaciones y Composición
        for assoc in model.associations:
            check_id(assoc.id, "UmlAssociation")
            end_a, end_b = assoc.member_ends

            for idx, end in enumerate([end_a, end_b]):
                if end.class_id not in classifier_ids:
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-11",
                            message=f"Extremo de asociación {idx} apunta a una clase inexistente ('{end.class_id}').",
                            severity=ValidationSeverity.ERROR,
                            element_id=assoc.id,
                        )
                    )

            # Invariante de Composición: El extremo del compuesto no puede tener upper > 1
            if end_a.aggregation_kind == AggregationKind.COMPOSITE:
                if end_a.multiplicity.upper is not None and end_a.multiplicity.upper > 1:
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-12",
                            message="En una composición, la multiplicidad del extremo compuesto no puede superar 1.",
                            severity=ValidationSeverity.ERROR,
                            element_id=assoc.id,
                        )
                    )
            if end_b.aggregation_kind == AggregationKind.COMPOSITE:
                if end_b.multiplicity.upper is not None and end_b.multiplicity.upper > 1:
                    result.issues.append(
                        ValidationIssue(
                            code="VUML-12",
                            message="En una composición, la multiplicidad del extremo compuesto no puede superar 1.",
                            severity=ValidationSeverity.ERROR,
                            element_id=assoc.id,
                        )
                    )

        return result


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
