"""
UML Domain Model V2 - Implementación Pura de Dominio (OMG UML 2.5)

Este módulo contiene las estructuras de datos y entidades canónicas de diagramas
de clases UML 2.5. Es completamente agnóstico de frameworks (sin Pydantic, SQLAlchemy,
FastAPI, Django ni librerías de UI).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import uuid

from core.uml_domain.events import (
    DomainEvent,
    ElementoAgregado,
    LienzoCreado,
    RelacionAgregada,
    ElementoEliminado,
)
from core.uml_domain.exceptions import (
    ElementoNoEncontrado,
    UmlValidationError,
)


class VisibilityKind(str, Enum):
    PUBLIC = "+"
    PRIVATE = "-"
    PROTECTED = "#"
    PACKAGE = "~"

    @classmethod
    def from_symbol_or_str(cls, val: Optional[str]) -> "VisibilityKind":
        if not val:
            return cls.PRIVATE
        val = val.strip()
        for member in cls:
            if val == member.value or val.upper() == member.name:
                return member
        return cls.PRIVATE


class AggregationKind(str, Enum):
    """
    En UML 2.5, agregación y composición son modalidades de extremo de asociación.
    """
    NONE = "none"             # Asociación binaria regular
    SHARED = "shared"         # Agregación (rombo hueco)
    COMPOSITE = "composite"   # Composición existencial (rombo relleno)


class ParameterDirectionKind(str, Enum):
    IN = "in"
    OUT = "out"
    INOUT = "inout"
    RETURN = "return"


@dataclass(frozen=True)
class MultiplicityRange:
    """
    Representación estructurada de cardinalidad UML con cotas enteras.
    upper=None representa '*' (ilimitado/muchos).
    """
    lower: int
    upper: Optional[int] = None

    def __post_init__(self):
        if self.lower < 0:
            raise ValueError(f"La cota inferior no puede ser negativa: {self.lower}")
        if self.upper is not None and self.upper < self.lower:
            raise ValueError(
                f"La cota superior ({self.upper}) no puede ser menor a la inferior ({self.lower})"
            )

    @property
    def is_many(self) -> bool:
        return self.upper is None or self.upper > 1

    @property
    def is_optional(self) -> bool:
        return self.lower == 0

    def to_uml_str(self) -> str:
        if self.upper is None:
            return "*" if self.lower == 0 else f"{self.lower}..*"
        if self.lower == self.upper:
            return str(self.lower)
        return f"{self.lower}..{self.upper}"


@dataclass
class UmlParameter:
    """Parámetro formal de una operación/método."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: str = "String"
    direction: ParameterDirectionKind = ParameterDirectionKind.IN
    default_value: Optional[str] = None
    multiplicity: MultiplicityRange = field(default_factory=lambda: MultiplicityRange(1, 1))


@dataclass
class UmlOperation:
    """Método u operación de un clasificador."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    return_type: str = "void"
    visibility: VisibilityKind = VisibilityKind.PUBLIC
    parameters: List[UmlParameter] = field(default_factory=list)
    is_static: bool = False
    is_abstract: bool = False


@dataclass
class UmlAttribute:
    """Propiedad estructural de un clasificador."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    type: str = "String"
    visibility: VisibilityKind = VisibilityKind.PRIVATE
    default_value: Optional[str] = None
    multiplicity: MultiplicityRange = field(default_factory=lambda: MultiplicityRange(1, 1))
    is_static: bool = False
    is_read_only: bool = False
    is_derived: bool = False


@dataclass
class UmlClassifier:
    """Clase base para clasificadores UML."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    visibility: VisibilityKind = VisibilityKind.PUBLIC
    documentation: Optional[str] = None


@dataclass
class UmlClass(UmlClassifier):
    """Clase UML concreta o abstracta."""
    is_abstract: bool = False
    is_interface: bool = False
    stereotype: Optional[str] = None
    attributes: List[UmlAttribute] = field(default_factory=list)
    operations: List[UmlOperation] = field(default_factory=list)


@dataclass
class UmlInterface(UmlClassifier):
    """Interfaz UML formal."""
    operations: List[UmlOperation] = field(default_factory=list)


@dataclass
class UmlEnumeration(UmlClassifier):
    """Enumeración UML."""
    literals: List[str] = field(default_factory=list)


@dataclass
class UmlDataType(UmlClassifier):
    """Tipo de dato de usuario."""
    attributes: List[UmlAttribute] = field(default_factory=list)


@dataclass
class AssociationEnd:
    """
    Extremo de una asociación.
    El aggregation_kind determina si este extremo actúa como un todo
    (SHARED para agregación, COMPOSITE para composición).
    """
    class_id: str
    role_name: Optional[str] = None
    multiplicity: MultiplicityRange = field(default_factory=lambda: MultiplicityRange(1, 1))
    is_navigable: bool = True
    aggregation_kind: AggregationKind = AggregationKind.NONE


@dataclass
class UmlAssociation:
    """
    Asociación binaria estructural entre dos clasificadores.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    member_ends: Tuple[AssociationEnd, AssociationEnd] = field(
        default_factory=lambda: (AssociationEnd(class_id=""), AssociationEnd(class_id=""))
    )


@dataclass
class UmlGeneralization:
    """
    Relación taxonómica de herencia (substitución) entre subclase y superclase.
    Semántica propia: No posee multiplicidades ni roles.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    specific_class_id: str = ""  # Subclase
    general_class_id: str = ""   # Superclase


@dataclass
class UmlRealization:
    """
    Relación de implementación contractual de una interfaz por una clase cliente.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_class_id: str = ""        # Clase implementadora
    supplier_interface_id: str = ""  # Interfaz implementada


@dataclass
class UmlDependency:
    """
    Relación de uso o dependencia débil entre clasificadores.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    client_class_id: str = ""
    supplier_class_id: str = ""


# ==============================================================================
# SEPARACIÓN ESTRICTA DE LAYOUT VISUAL (Opcional e Independiente)
# ==============================================================================

@dataclass
class ElementLayout:
    x: float = 0.0
    y: float = 0.0
    width: float = 180.0
    height: float = 120.0


@dataclass
class RelationshipLayout:
    vertices: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class ViewportLayout:
    zoom: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0


@dataclass
class UmlVisualLayout:
    viewport: ViewportLayout = field(default_factory=ViewportLayout)
    nodes: Dict[str, ElementLayout] = field(default_factory=dict)
    links: Dict[str, RelationshipLayout] = field(default_factory=dict)


# ==============================================================================
# MODELO RAÍZ CANÓNICO
# ==============================================================================

@dataclass
class UmlDomainModel:
    """
    Modelo de dominio UML 2.5 canónico e independiente.
    """
    schema_version: str = "2.0.0"
    model_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "UmlModel"
    description: Optional[str] = None
    classes: List[UmlClass] = field(default_factory=list)
    interfaces: List[UmlInterface] = field(default_factory=list)
    enumerations: List[UmlEnumeration] = field(default_factory=list)
    data_types: List[UmlDataType] = field(default_factory=list)
    associations: List[UmlAssociation] = field(default_factory=list)
    generalizations: List[UmlGeneralization] = field(default_factory=list)
    realizations: List[UmlRealization] = field(default_factory=list)
    dependencies: List[UmlDependency] = field(default_factory=list)
    visual_layout: Optional[UmlVisualLayout] = None

    def find_classifier_by_id(self, cid: str) -> Optional[UmlClassifier]:
        for c in self.classes:
            if c.id == cid:
                return c
        for i in self.interfaces:
            if i.id == cid:
                return i
        for e in self.enumerations:
            if e.id == cid:
                return e
        for d in self.data_types:
            if d.id == cid:
                return d
        return None

    def find_classifier_by_name(self, name: str) -> Optional[UmlClassifier]:
        name_lower = name.strip().lower()
        for c in self.classes:
            if c.name.strip().lower() == name_lower:
                return c
        for i in self.interfaces:
            if i.name.strip().lower() == name_lower:
                return i
        for e in self.enumerations:
            if e.name.strip().lower() == name_lower:
                return e
        for d in self.data_types:
            if d.name.strip().lower() == name_lower:
                return d
        return None

    # -- Métodos de mutación explícita orientada a eventos -----------------

    def agregar_clase(self, nombre: str, is_abstract: bool = False) -> Tuple[UmlClass, DomainEvent]:
        """CU3: Gestionar elementos del diagrama de clases (creación)."""
        if self.find_classifier_by_name(nombre) is not None:
            raise UmlValidationError(f"Ya existe un clasificador llamado '{nombre}' en este modelo.")
        clase = UmlClass(id=str(uuid.uuid4()), name=nombre, is_abstract=is_abstract)
        self.classes.append(clase)
        return clase, ElementoAgregado(elemento_id=clase.id, tipo="UmlClass")

    def agregar_asociacion(
        self,
        origen_id: str,
        destino_id: str,
        nombre: Optional[str] = None,
        rol_origen: Optional[str] = None,
        rol_destino: Optional[str] = None,
        multiplicidad_origen: Optional[MultiplicityRange] = None,
        multiplicidad_destino: Optional[MultiplicityRange] = None,
        agregacion_origen: AggregationKind = AggregationKind.NONE,
        agregacion_destino: AggregationKind = AggregationKind.NONE,
    ) -> Tuple[UmlAssociation, DomainEvent]:
        """CU4: Gestionar relaciones del diagrama de clases (creación)."""
        if self.find_classifier_by_id(origen_id) is None:
            raise ElementoNoEncontrado(f"El elemento origen '{origen_id}' no existe en el modelo.")
        if self.find_classifier_by_id(destino_id) is None:
            raise ElementoNoEncontrado(f"El elemento destino '{destino_id}' no existe en el modelo.")

        end1 = AssociationEnd(
            class_id=origen_id,
            role_name=rol_origen,
            multiplicity=multiplicidad_origen or MultiplicityRange(1, 1),
            aggregation_kind=agregacion_origen,
        )
        end2 = AssociationEnd(
            class_id=destino_id,
            role_name=rol_destino,
            multiplicity=multiplicidad_destino or MultiplicityRange(1, 1),
            aggregation_kind=agregacion_destino,
        )
        asociacion = UmlAssociation(
            id=str(uuid.uuid4()),
            name=nombre,
            member_ends=(end1, end2),
        )
        self.associations.append(asociacion)
        return asociacion, RelacionAgregada(relacion_id=asociacion.id, tipo="UmlAssociation")


# ==============================================================================
# LIENZO DE TRABAJO (Canvas)
# ==============================================================================

@dataclass
class Lienzo:
    """
    Lienzo de trabajo que encapsula el modelo semántico y el layout visual.
    Reutiliza model_id como su propio identificador único.
    """
    modelo: UmlDomainModel
    visual_layout: Dict[str, Any] = field(default_factory=dict)
    creado_en: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def id(self) -> str:
        return self.modelo.model_id

    @staticmethod
    def crear_nuevo() -> Tuple["Lienzo", DomainEvent]:
        """CU1: Crear nuevo lienzo UML."""
        modelo = UmlDomainModel()
        lienzo = Lienzo(modelo=modelo)
        return lienzo, LienzoCreado(lienzo_id=modelo.model_id)

