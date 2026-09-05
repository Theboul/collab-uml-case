# Borrador de Especificación del Contrato de Serialización V2

> [!IMPORTANT]
> Conforme a las decisiones arquitectónicas de la SPEC-03, este documento define la **especificación del contrato de serialización** (`contracts/uml-model.v2.json`), el cual representa la especificación de datos portable para intercambio entre subsistemas. El modelo de dominio en memoria es independiente de este formato de transporte.

---

## 1. Estructura y Esquema de Serialización Propuesto

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://diagramador-uml.org/contracts/uml-model.v2.json",
  "title": "UmlClassDiagramContractV2",
  "type": "object",
  "required": ["schemaVersion", "modelId", "name", "classes"],
  "properties": {
    "schemaVersion": {
      "type": "string",
      "const": "2.0.0"
    },
    "modelId": {
      "type": "string",
      "format": "uuid"
    },
    "name": {
      "type": "string",
      "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"
    },
    "description": {
      "type": ["string", "null"]
    },
    "classes": {
      "type": "array",
      "items": { "$ref": "#/$defs/ClassDefinition" }
    },
    "associations": {
      "type": "array",
      "items": { "$ref": "#/$defs/AssociationDefinition" },
      "default": []
    },
    "generalizations": {
      "type": "array",
      "items": { "$ref": "#/$defs/GeneralizationDefinition" },
      "default": []
    },
    "realizations": {
      "type": "array",
      "items": { "$ref": "#/$defs/RealizationDefinition" },
      "default": []
    },
    "dependencies": {
      "type": "array",
      "items": { "$ref": "#/$defs/DependencyDefinition" },
      "default": []
    },
    "visualLayout": {
      "type": ["object", "null"],
      "$ref": "#/$defs/VisualLayoutDefinition",
      "default": null
    }
  },
  "$defs": {
    "Visibility": {
      "type": "string",
      "enum": ["+", "-", "#", "~"]
    },
    "AggregationKind": {
      "type": "string",
      "enum": ["none", "shared", "composite"]
    },
    "Multiplicity": {
      "type": "object",
      "required": ["lowerBound"],
      "properties": {
        "lowerBound": { "type": "integer", "minimum": 0 },
        "upperBound": { "type": ["integer", "null"], "minimum": 0 }
      }
    },
    "ParameterDefinition": {
      "type": "object",
      "required": ["name", "type"],
      "properties": {
        "name": { "type": "string" },
        "type": { "type": "string" },
        "direction": { "type": "string", "enum": ["in", "out", "inout", "return"], "default": "in" },
        "defaultValue": { "type": ["string", "null"] }
      }
    },
    "OperationDefinition": {
      "type": "object",
      "required": ["id", "name", "returnType"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "name": { "type": "string" },
        "visibility": { "$ref": "#/$defs/Visibility", "default": "+" },
        "returnType": { "type": "string" },
        "isStatic": { "type": "boolean", "default": false },
        "isAbstract": { "type": "boolean", "default": false },
        "parameters": {
          "type": "array",
          "items": { "$ref": "#/$defs/ParameterDefinition" }
        }
      }
    },
    "AttributeDefinition": {
      "type": "object",
      "required": ["id", "name", "type"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "name": { "type": "string" },
        "type": { "type": "string" },
        "visibility": { "$ref": "#/$defs/Visibility", "default": "-" },
        "defaultValue": { "type": ["string", "null"] },
        "isStatic": { "type": "boolean", "default": false },
        "isReadOnly": { "type": "boolean", "default": false },
        "multiplicity": { "$ref": "#/$defs/Multiplicity" }
      }
    },
    "ClassDefinition": {
      "type": "object",
      "required": ["id", "name"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "name": { "type": "string" },
        "visibility": { "$ref": "#/$defs/Visibility", "default": "+" },
        "isAbstract": { "type": "boolean", "default": false },
        "isInterface": { "type": "boolean", "default": false },
        "stereotype": { "type": ["string", "null"] },
        "attributes": {
          "type": "array",
          "items": { "$ref": "#/$defs/AttributeDefinition" }
        },
        "operations": {
          "type": "array",
          "items": { "$ref": "#/$defs/OperationDefinition" }
        }
      }
    },
    "AssociationEnd": {
      "type": "object",
      "required": ["classId", "multiplicity"],
      "properties": {
        "classId": { "type": "string", "format": "uuid" },
        "roleName": { "type": ["string", "null"] },
        "isNavigable": { "type": "boolean", "default": true },
        "aggregationKind": { "$ref": "#/$defs/AggregationKind", "default": "none" },
        "multiplicity": { "$ref": "#/$defs/Multiplicity" }
      }
    },
    "AssociationDefinition": {
      "type": "object",
      "required": ["id", "memberEnds"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "name": { "type": ["string", "null"] },
        "memberEnds": {
          "type": "array",
          "minItems": 2,
          "maxItems": 2,
          "items": { "$ref": "#/$defs/AssociationEnd" }
        }
      }
    },
    "GeneralizationDefinition": {
      "type": "object",
      "required": ["id", "specificClassId", "generalClassId"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "specificClassId": { "type": "string", "format": "uuid" },
        "generalClassId": { "type": "string", "format": "uuid" }
      }
    },
    "RealizationDefinition": {
      "type": "object",
      "required": ["id", "clientClassId", "supplierInterfaceId"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "clientClassId": { "type": "string", "format": "uuid" },
        "supplierInterfaceId": { "type": "string", "format": "uuid" }
      }
    },
    "DependencyDefinition": {
      "type": "object",
      "required": ["id", "clientClassId", "supplierClassId"],
      "properties": {
        "id": { "type": "string", "format": "uuid" },
        "clientClassId": { "type": "string", "format": "uuid" },
        "supplierClassId": { "type": "string", "format": "uuid" }
      }
    },
    "VisualLayoutDefinition": {
      "type": "object",
      "properties": {
        "viewport": {
          "type": "object",
          "properties": {
            "zoom": { "type": "number" },
            "panX": { "type": "number" },
            "panY": { "type": "number" }
          }
        },
        "nodes": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "required": ["x", "y", "width", "height"],
            "properties": {
              "x": { "type": "number" },
              "y": { "type": "number" },
              "width": { "type": "number" },
              "height": { "type": "number" }
            }
          }
        },
        "links": {
          "type": "object",
          "additionalProperties": {
            "type": "object",
            "properties": {
              "vertices": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["x", "y"],
                  "properties": {
                    "x": { "type": "number" },
                    "y": { "type": "number" }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 2. Ejemplo Representativo de Payload Canónico V2

```json
{
  "schemaVersion": "2.0.0",
  "modelId": "c8f2b7a1-5d9e-4e3f-b2c6-1a8e9d0f3b4a",
  "name": "SistemaVentas",
  "description": "Diagrama de clases para módulo de facturación y pedidos",
  "classes": [
    {
      "id": "e4b1c7d2-3a9f-4b8c-9e2d-1f0a8b7c6d5e",
      "name": "Cliente",
      "visibility": "+",
      "isAbstract": false,
      "isInterface": false,
      "stereotype": null,
      "attributes": [
        {
          "id": "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d",
          "name": "ruc",
          "type": "String",
          "visibility": "-",
          "defaultValue": null,
          "isStatic": false,
          "isReadOnly": true,
          "multiplicity": { "lowerBound": 1, "upperBound": 1 }
        }
      ],
      "operations": [
        {
          "id": "f1e2d3c4-b5a6-4f7e-8d9c-0b1a2c3d4e5f",
          "name": "verificarCredito",
          "visibility": "+",
          "returnType": "Boolean",
          "isStatic": false,
          "isAbstract": false,
          "parameters": [
            { "name": "monto", "type": "Float", "direction": "in", "defaultValue": null }
          ]
        }
      ]
    },
    {
      "id": "b7c8d9e0-1f2a-4b3c-9d4e-5f6a7b8c9d0e",
      "name": "Pedido",
      "visibility": "+",
      "isAbstract": false,
      "isInterface": false,
      "stereotype": null,
      "attributes": [
        {
          "id": "c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f",
          "name": "numeroPedido",
          "type": "String",
          "visibility": "-",
          "defaultValue": null,
          "isStatic": false,
          "isReadOnly": true,
          "multiplicity": { "lowerBound": 1, "upperBound": 1 }
        }
      ],
      "operations": []
    },
    {
      "id": "d0e1f2a3-b4c5-4d6e-8f9a-0b1c2d3e4f5a",
      "name": "ItemPedido",
      "visibility": "+",
      "isAbstract": false,
      "isInterface": false,
      "stereotype": null,
      "attributes": [
        {
          "id": "e2f3a4b5-c6d7-4e8f-9a0b-1c2d3e4f5a6b",
          "name": "cantidad",
          "type": "Integer",
          "visibility": "-",
          "defaultValue": "1",
          "isStatic": false,
          "isReadOnly": false,
          "multiplicity": { "lowerBound": 1, "upperBound": 1 }
        }
      ],
      "operations": []
    }
  ],
  "associations": [
    {
      "id": "assoc-cliente-pedido",
      "name": "realiza",
      "memberEnds": [
        {
          "classId": "e4b1c7d2-3a9f-4b8c-9e2d-1f0a8b7c6d5e",
          "roleName": "cliente",
          "isNavigable": true,
          "aggregationKind": "none",
          "multiplicity": { "lowerBound": 1, "upperBound": 1 }
        },
        {
          "classId": "b7c8d9e0-1f2a-4b3c-9d4e-5f6a7b8c9d0e",
          "roleName": "pedidos",
          "isNavigable": true,
          "aggregationKind": "none",
          "multiplicity": { "lowerBound": 0, "upperBound": null }
        }
      ]
    },
    {
      "id": "assoc-pedido-item",
      "name": null,
      "memberEnds": [
        {
          "classId": "b7c8d9e0-1f2a-4b3c-9d4e-5f6a7b8c9d0e",
          "roleName": "pedido",
          "isNavigable": true,
          "aggregationKind": "composite",
          "multiplicity": { "lowerBound": 1, "upperBound": 1 }
        },
        {
          "classId": "d0e1f2a3-b4c5-4d6e-8f9a-0b1c2d3e4f5a",
          "roleName": "items",
          "isNavigable": true,
          "aggregationKind": "none",
          "multiplicity": { "lowerBound": 1, "upperBound": null }
        }
      ]
    }
  ],
  "generalizations": [],
  "realizations": [],
  "dependencies": [],
  "visualLayout": {
    "viewport": { "zoom": 1.0, "panX": 0, "panY": 0 },
    "nodes": {
      "e4b1c7d2-3a9f-4b8c-9e2d-1f0a8b7c6d5e": { "x": 80, "y": 120, "width": 220, "height": 160 },
      "b7c8d9e0-1f2a-4b3c-9d4e-5f6a7b8c9d0e": { "x": 420, "y": 120, "width": 220, "height": 140 },
      "d0e1f2a3-b4c5-4d6e-8f9a-0b1c2d3e4f5a": { "x": 750, "y": 120, "width": 200, "height": 130 }
    },
    "links": {
      "assoc-cliente-pedido": { "vertices": [] },
      "assoc-pedido-item": { "vertices": [] }
    }
  }
}
```
