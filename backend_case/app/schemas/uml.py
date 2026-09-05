"""
Esquemas Pydantic v2 exclusivos para frontera HTTP (Request / Response DTOs).
Conformes estrictamente con contracts/uml-model.v2.json.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MultiplicitySchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    lowerBound: int = Field(..., ge=0, description="Cota inferior >= 0")
    upperBound: int | None = Field(None, ge=0, description="Cota superior (null representa '*')")


class ParameterSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    type: str
    direction: Literal["in", "out", "inout", "return"] = "in"
    defaultValue: str | None = None


class OperationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    visibility: Literal["+", "-", "#", "~"] = "+"
    returnType: str
    isStatic: bool = False
    isAbstract: bool = False
    parameters: list[ParameterSchema] = Field(default_factory=list)


class AttributeSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    type: str
    visibility: Literal["+", "-", "#", "~"] = "-"
    defaultValue: str | None = None
    isStatic: bool = False
    isReadOnly: bool = False
    multiplicity: MultiplicitySchema | None = None


class ClassSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    visibility: Literal["+", "-", "#", "~"] = "+"
    isAbstract: bool = False
    isInterface: bool = False
    stereotype: str | None = None
    attributes: list[AttributeSchema] = Field(default_factory=list)
    operations: list[OperationSchema] = Field(default_factory=list)


class AssociationEndSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    classId: str
    roleName: str | None = None
    isNavigable: bool = True
    aggregationKind: Literal["none", "shared", "composite"] = "none"
    multiplicity: MultiplicitySchema


class AssociationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str | None = None
    memberEnds: list[AssociationEndSchema] = Field(..., min_length=2, max_length=2)


class GeneralizationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    specificClassId: str
    generalClassId: str


class RealizationSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    clientClassId: str
    supplierInterfaceId: str


class DependencySchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    clientClassId: str
    supplierClassId: str


class UmlModelSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schemaVersion: str = Field(default="2.0.0", pattern=r"^2\.\d+\.\d+$")
    modelId: str
    name: str
    description: str | None = None
    classes: list[ClassSchema] = Field(default_factory=list)
    associations: list[AssociationSchema] = Field(default_factory=list)
    generalizations: list[GeneralizationSchema] = Field(default_factory=list)
    realizations: list[RealizationSchema] = Field(default_factory=list)
    dependencies: list[DependencySchema] = Field(default_factory=list)
    visualLayout: dict[str, Any] | None = None


# ==============================================================================
# DTOs para Respuestas de Validación
# ==============================================================================

class ValidationIssueSchema(BaseModel):
    code: str
    message: str
    severity: Literal["ERROR", "WARNING"]
    elementId: str | None = None


class ValidationResponseSchema(BaseModel):
    valid: bool
    errors: list[ValidationIssueSchema] = Field(default_factory=list)
    warnings: list[ValidationIssueSchema] = Field(default_factory=list)
