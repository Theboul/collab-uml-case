"""
Esquemas Pydantic v2 para comandos semánticos del editor UML (CU3).
Contratos fuertemente tipados sin estructuras genéricas no validadas.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend_case.app.schemas.uml import ClassSchema, ParameterSchema
from core.uml_domain.model import VisibilityKind

RelationType = Literal["ASSOCIATION", "AGGREGATION", "COMPOSITION", "DEPENDENCY"]


class ElementLayoutSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    elementId: str
    x: float
    y: float
    width: float
    height: float


class RelationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: RelationType = "ASSOCIATION"
    sourceClassId: str
    targetClassId: str
    sourceMultiplicity: str = "1"
    targetMultiplicity: str = "1"
    sourceRole: str | None = None
    targetRole: str | None = None
    name: str | None = None


class GeneralizationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    specificClassId: str
    generalClassId: str


# ---------------------------------------------------------------------------
# Comandos de Clase (CU1 / CU3)
# ---------------------------------------------------------------------------

class CreateClassCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str | None = None
    name: str = Field(..., min_length=1, max_length=255)
    isAbstract: bool = False
    x: float = 100.0
    y: float = 100.0
    width: float = 190.0
    height: float = 130.0


class UpdateClassNameCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    name: str = Field(..., min_length=1, max_length=255)


class DeleteElementsCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classIds: list[str] = Field(..., min_length=1)


class RestoreElementsCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classes: list[ClassSchema] = Field(default_factory=list)
    relations: list[RelationSchema] = Field(default_factory=list)
    generalizations: list[GeneralizationSchema] = Field(default_factory=list)
    layouts: list[ElementLayoutSchema] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Comandos de Atributos (CU3)
# ---------------------------------------------------------------------------

class AddAttributeCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)
    visibility: VisibilityKind = VisibilityKind.PRIVATE
    isStatic: bool = False


class UpdateAttributeCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    attributeId: str
    name: str | None = None
    type: str | None = None
    visibility: VisibilityKind | None = None
    isStatic: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "UpdateAttributeCommand":
        if self.name is None and self.type is None and self.visibility is None and self.isStatic is None:
            raise ValueError("EMPTY_UPDATE: Se debe proporcionar al menos un campo a modificar.")
        if self.name is not None and not self.name.strip():
            raise ValueError("ATTRIBUTE_NAME_REQUIRED: El nombre del atributo no puede estar vacío.")
        if self.type is not None and not self.type.strip():
            raise ValueError("ATTRIBUTE_TYPE_REQUIRED: El tipo del atributo no puede estar vacío.")
        return self


class DeleteAttributeCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    attributeId: str


# ---------------------------------------------------------------------------
# Comandos de Operaciones (CU3)
# ---------------------------------------------------------------------------

class AddOperationCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=255)
    returnType: str = Field(default="void", min_length=1, max_length=255)
    visibility: VisibilityKind = VisibilityKind.PUBLIC
    parameters: list[ParameterSchema] = Field(default_factory=list)
    isStatic: bool = False
    isAbstract: bool = False


class UpdateOperationCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    operationId: str
    name: str | None = None
    returnType: str | None = None
    visibility: VisibilityKind | None = None
    isStatic: bool | None = None
    isAbstract: bool | None = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "UpdateOperationCommand":
        if (
            self.name is None
            and self.returnType is None
            and self.visibility is None
            and self.isStatic is None
            and self.isAbstract is None
        ):
            raise ValueError("EMPTY_UPDATE: Se debe proporcionar al menos un campo a modificar.")
        if self.name is not None and not self.name.strip():
            raise ValueError("OPERATION_NAME_REQUIRED: El nombre de la operación no puede estar vacío.")
        return self


class DeleteOperationCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    operationId: str


# ---------------------------------------------------------------------------
# Comandos de Parámetros (CU3)
# ---------------------------------------------------------------------------

class AddParameterCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    operationId: str
    id: str | None = None
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=255)


class UpdateParameterCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    operationId: str
    parameterId: str
    name: str | None = None
    type: str | None = None

    @model_validator(mode="after")
    def validate_non_empty(self) -> "UpdateParameterCommand":
        if self.name is None and self.type is None:
            raise ValueError("EMPTY_UPDATE: Se debe proporcionar al menos un campo a modificar.")
        if self.name is not None and not self.name.strip():
            raise ValueError("PARAMETER_NAME_REQUIRED: El nombre del parámetro no puede estar vacío.")
        if self.type is not None and not self.type.strip():
            raise ValueError("PARAMETER_TYPE_REQUIRED: El tipo del parámetro no puede estar vacío.")
        return self


class DeleteParameterCommand(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    operationId: str
    parameterId: str
