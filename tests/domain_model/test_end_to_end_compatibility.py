"""
Pruebas de aceptación End-to-End: Demostración del pipeline completo (Sección 27 de SPEC-05).
F08 Legacy -> LegacyInputAdapter -> UML Domain Model V2 -> Validar -> Mapper -> Generadores existentes.
"""

import json
from pathlib import Path
import shutil
import tempfile
import pytest

from core.uml_domain.adapters.legacy_input_adapter import LegacyInputAdapter
from core.uml_domain.adapters.spring_legacy_mapper import SpringLegacyMapper
from core.uml_domain.adapters.flutter_legacy_mapper import FlutterLegacyMapper
from core.uml_domain.validation import UMLValidator
from tests.spring_generator.test_spring_generator_characterization import SpringGeneratorSimulator

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
from mobile_app_reference import FlutterCRUDGenerator

FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "legacy"


def test_f08_end_to_end_spring_pipeline():
    """
    Criterio de Aceptación Principal (Spring Boot):
    F08 Legacy -> LegacyInputAdapter -> UML Domain Model V2 -> Validar -> SpringLegacyMapper -> Spring Simulator
    """
    with open(FIXTURES_DIR / "F08-combined-model.json", "r", encoding="utf-8") as f:
        f08_raw = json.load(f)

    # 1. Ingesta a V2
    model_v2 = LegacyInputAdapter.to_v2_model(f08_raw, model_name="SistemaVentasV2")
    assert model_v2.schema_version == "2.0.0"

    # 2. Validación Semántica UML 2.5
    validator = UMLValidator()
    val_result = validator.validate(model_v2)
    assert val_result.is_valid, f"Errores semánticos: {[e.message for e in val_result.errors]}"

    # 3. Mapeo hacia contrato Spring Boot
    spring_tx = SpringLegacyMapper.to_spring_schema(model_v2)
    assert spring_tx.report.is_compatible, f"Incompatible con Spring: {spring_tx.report.unsupported_errors}"

    # 4. Alimentar el Generador Spring Boot existente
    sim = SpringGeneratorSimulator(spring_tx.payload)
    meta = sim.build_generation_metadata()

    # Verificar que todas las entidades de F08 fueron generadas
    expected_classes = ["Persona", "Empleado", "Cliente", "Pedido", "DetallePedido", "Producto"]
    for ec in expected_classes:
        assert ec in meta["classes"]

    # Verificar herencia en Empleado
    assert meta["entitiesMetadata"]["Empleado"]["isChild"] is True
    assert meta["entitiesMetadata"]["Empleado"]["parentClass"] == "Persona"

    # Verificar composición en Pedido -> DetallePedido
    pedido_one_to_many = meta["entitiesMetadata"]["Pedido"]["oneToMany"]
    assert any(r["target"] == "DetallePedido" and r["composition"] is True for r in pedido_one_to_many)


def test_f08_end_to_end_flutter_pipeline():
    """
    Criterio de Aceptación Principal (Flutter CRUD):
    F08 Legacy -> LegacyInputAdapter -> UML Domain Model V2 -> Validar -> FlutterLegacyMapper -> FlutterCRUDGenerator
    """
    with open(FIXTURES_DIR / "F08-combined-model.json", "r", encoding="utf-8") as f:
        f08_raw = json.load(f)

    # 1. Ingesta a V2
    model_v2 = LegacyInputAdapter.to_v2_model(f08_raw, model_name="SistemaVentasV2")

    # 2. Validación Semántica UML 2.5
    validator = UMLValidator()
    val_result = validator.validate(model_v2)
    assert val_result.is_valid

    # 3. Mapeo hacia contrato Flutter CRUD
    flutter_tx = FlutterLegacyMapper.to_flutter_json(model_v2)
    assert flutter_tx.report.is_compatible

    # 4. Alimentar el FlutterCRUDGenerator real sin modificarlo
    temp_dir = Path(tempfile.mkdtemp()) / "flutter_f08_app"
    try:
        generator = FlutterCRUDGenerator(flutter_tx.payload)
        generator.generate_project(output_dir=temp_dir)

        # Verificar generación de modelos y vistas reales
        assert (temp_dir / "pubspec.yaml").exists()
        assert (temp_dir / "lib" / "main.dart").exists()

        for cname in ["cliente", "pedido", "detalle_pedido", "producto", "persona", "empleado"]:
            assert (temp_dir / "lib" / "models" / f"{cname}.dart").exists()
            assert (temp_dir / "lib" / "views" / f"{cname}_list_view.dart").exists()
            assert (temp_dir / "lib" / "views" / f"{cname}_form_view.dart").exists()
    finally:
        shutil.rmtree(temp_dir.parent, ignore_errors=True)
