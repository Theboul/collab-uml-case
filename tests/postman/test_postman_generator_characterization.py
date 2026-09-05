import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "legacy"


class PostmanCollectionSimulator:
    """
    Simulador que reproduce con fidelidad la lógica exacta de
    `back_generator_uml/src/main/java/generator_uml/back_generator_uml/service/PostmanCollectionGenerator.java`.
    """
    def __init__(self, schema, base_url="http://localhost:9000", artifact_id="mi-proyecto"):
        self.schema = schema
        self.base_url = base_url
        self.artifact_id = artifact_id

    def generate(self):
        classes = self.schema.get("classes", [])
        relationships = self.schema.get("relationships", [])

        collection = {
            "info": {
                "name": f"{self.artifact_id} API Collection",
                "description": f"Colección generada automáticamente para {self.artifact_id}",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "variable": [
                {
                    "key": "baseUrl",
                    "value": self.base_url,
                    "type": "string"
                }
            ],
            "item": []
        }

        # Detectar ManyToMany para registrar entidades intermedias
        intermediate_entities = set()
        for rel in relationships:
            rtype = rel.get("type", "").lower()
            if rtype in ["association", "aggregation", "composition", "dependency"]:
                src = next((c["name"] for c in classes if c["id"] == rel.get("sourceId")), None)
                tgt = next((c["name"] for c in classes if c["id"] == rel.get("targetId")), None)
                if not src or not tgt:
                    continue

                labels = rel.get("labels", [])
                s_card = labels[0].strip() if len(labels) > 0 and labels[0] else ("*" if rtype == "dependency" else "")
                t_card = labels[1].strip() if len(labels) > 1 and labels[1] else ("1" if rtype == "dependency" else "")

                if "*" in s_card and "*" in t_card:
                    first = src if src < tgt else tgt
                    second = tgt if src < tgt else src
                    intermediate_entities.add(first + second)

        # Generar carpetas y requests para clases normales
        for c in classes:
            name = c["name"]
            plural = name.lower()

            # Mock de atributos de ejemplo
            sample_body = {}
            for attr in c.get("attributes", []):
                aname = attr["name"]
                atype = attr.get("type", "String").lower()
                if "int" in atype or "long" in atype:
                    sample_body[aname] = 1
                elif "double" in atype or "float" in atype:
                    sample_body[aname] = 10.5
                elif "bool" in atype:
                    sample_body[aname] = True
                else:
                    sample_body[aname] = f"ejemplo_{aname}"

            folder = {
                "name": name,
                "item": [
                    {
                        "name": f"Listar {name}",
                        "request": {
                            "method": "GET",
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural]
                            }
                        }
                    },
                    {
                        "name": f"Obtener {name} por ID",
                        "request": {
                            "method": "GET",
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}/1",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural, "1"]
                            }
                        }
                    },
                    {
                        "name": f"Crear {name}",
                        "request": {
                            "method": "POST",
                            "header": [{"key": "Content-Type", "value": "application/json"}],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(sample_body, indent=2)
                            },
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural]
                            }
                        }
                    },
                    {
                        "name": f"Actualizar {name}",
                        "request": {
                            "method": "PUT",
                            "header": [{"key": "Content-Type", "value": "application/json"}],
                            "body": {
                                "mode": "raw",
                                "raw": json.dumps(sample_body, indent=2)
                            },
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}/1",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural, "1"]
                            }
                        }
                    },
                    {
                        "name": f"Eliminar {name}",
                        "request": {
                            "method": "DELETE",
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}/1",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural, "1"]
                            }
                        }
                    }
                ]
            }
            collection["item"].append(folder)

        # Agregar carpetas para entidades intermedias
        for ie in sorted(intermediate_entities):
            plural = ie.lower()
            folder = {
                "name": ie,
                "item": [
                    {
                        "name": f"Listar {ie}",
                        "request": {
                            "method": "GET",
                            "url": {
                                "raw": f"{{{{baseUrl}}}}/api/v1/{plural}",
                                "host": ["{{baseUrl}}"],
                                "path": ["api", "v1", plural]
                            }
                        }
                    }
                ]
            }
            collection["item"].append(folder)

        return collection


@pytest.fixture
def f01_json():
    with open(FIXTURES_DIR / "F01-simple-class.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def f08_json():
    with open(FIXTURES_DIR / "F08-combined-model.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_t_post_01_valid_collection_schema(f01_json):
    """T-POST-01: F01 produce una colección válida Postman v2.1.0."""
    gen = PostmanCollectionSimulator(f01_json, artifact_id="cliente-service")
    collection = gen.generate()

    assert "info" in collection
    assert collection["info"]["schema"] == "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    assert "cliente-service API Collection" in collection["info"]["name"]
    assert len(collection["variable"]) == 1
    assert collection["variable"][0]["key"] == "baseUrl"


def test_t_post_02_crud_operations(f01_json):
    """T-POST-02: Verificar las 5 operaciones CRUD (GET all, GET by id, POST, PUT, DELETE)."""
    gen = PostmanCollectionSimulator(f01_json)
    collection = gen.generate()

    cliente_folder = collection["item"][0]
    assert cliente_folder["name"] == "Cliente"

    requests = {req["request"]["method"]: req["name"] for req in cliente_folder["item"]}
    assert "GET" in requests
    assert "POST" in requests
    assert "PUT" in requests
    assert "DELETE" in requests
    assert len(cliente_folder["item"]) == 5


def test_t_post_03_example_body_generation(f01_json):
    """T-POST-03: Comprobar generación de bodies de ejemplo tipados en POST y PUT."""
    gen = PostmanCollectionSimulator(f01_json)
    collection = gen.generate()

    cliente_folder = collection["item"][0]
    post_req = next(r for r in cliente_folder["item"] if r["request"]["method"] == "POST")
    body_str = post_req["request"]["body"]["raw"]
    body_data = json.loads(body_str)

    assert "id" in body_data
    assert "nombre" in body_data
    assert "email" in body_data
    assert isinstance(body_data["id"], int)
    assert isinstance(body_data["nombre"], str)


def test_t_post_04_combined_model_coverage(f08_json):
    """T-POST-04: F08 produce carpetas y requests para todas las entidades modeladas."""
    gen = PostmanCollectionSimulator(f08_json)
    collection = gen.generate()

    folder_names = [folder["name"] for folder in collection["item"]]
    expected_classes = ["Persona", "Empleado", "Cliente", "Pedido", "DetallePedido", "Producto"]

    for ec in expected_classes:
        assert ec in folder_names, f"Falta carpeta Postman para la entidad {ec}"
