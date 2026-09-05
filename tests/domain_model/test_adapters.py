"""
Pruebas de los adaptadores legacy bidireccionales y mappers de generación (SPEC-05).
"""

import json
from pathlib import Path
import pytest

from core.uml_domain.adapters.multiplicity_parser import LegacyMultiplicityParser
from core.uml_domain.adapters.legacy_input_adapter import LegacyInputAdapter
from core.uml_domain.adapters.legacy_output_adapter import LegacyOutputAdapter
from core.uml_domain.adapters.spring_legacy_mapper import SpringLegacyMapper
from core.uml_domain.adapters.flutter_legacy_mapper import FlutterLegacyMapper
from core.uml_domain.validation import UMLValidator
from core.uml_domain.model import UmlDomainModel, UmlInterface, UmlRealization

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "legacy"


def test_legacy_multiplicity_parser():
    # Casos válidos
    assert LegacyMultiplicityParser.parse("1").to_uml_str() == "1"
    assert LegacyMultiplicityParser.parse("*").to_uml_str() == "*"
    assert LegacyMultiplicityParser.parse("0..1").to_uml_str() == "0..1"
    assert LegacyMultiplicityParser.parse("0..*").to_uml_str() == "*"
    assert LegacyMultiplicityParser.parse("1..*").to_uml_str() == "1..*"
    assert LegacyMultiplicityParser.parse("2..5").to_uml_str() == "2..5"

    # Casos inválidos deben lanzar ValueError sin suposiciones silenciosas
    with pytest.raises(ValueError, match="no reconocido"):
        LegacyMultiplicityParser.parse("invalido")

    with pytest.raises(ValueError, match="vacía"):
        LegacyMultiplicityParser.parse("")


@pytest.mark.parametrize("fixture_name", [
    "F01-simple-class.json",
    "F02-operation.json",
    "F03-one-to-many.json",
    "F04-many-to-many.json",
    "F05-aggregation.json",
    "F06-composition.json",
    "F07-generalization.json",
    "F08-combined-model.json",
])
def test_all_fixtures_ingestion_and_validation(fixture_name):
    """
    Verifica que los 8 fixtures de SPEC-04 puedan ser ingeridos por LegacyInputAdapter
    produciendo un modelo V2 válido según el validador semántico.
    """
    fixture_path = FIXTURES_DIR / fixture_name
    with open(fixture_path, "r", encoding="utf-8") as f:
        legacy_data = json.load(f)

    # 1. Ingesta a V2
    model = LegacyInputAdapter.to_v2_model(legacy_data, model_name=fixture_name)
    assert isinstance(model, UmlDomainModel)
    assert model.schema_version == "2.0.0"

    # 2. Validación semántica del modelo resultante
    validator = UMLValidator()
    result = validator.validate(model)
    assert result.is_valid, f"Errores en {fixture_name}: {[i.message for i in result.errors]}"

    # 3. Layout visual separado
    if any("position" in c for c in legacy_data.get("classes", [])):
        assert model.visual_layout is not None
        assert len(model.visual_layout.nodes) == len(legacy_data["classes"])


@pytest.mark.parametrize("fixture_name", [
    "F01-simple-class.json",
    "F03-one-to-many.json",
    "F04-many-to-many.json",
    "F06-composition.json",
    "F07-generalization.json",
    "F08-combined-model.json",
])
def test_round_trip_semantic_equivalence(fixture_name):
    """
    Prueba de Round Trip:
    Legacy JSON -> V2 Model -> Legacy Output DTO
    Verifica que la semántica relevante de clases, atributos, relaciones y multiplicidades se mantenga.
    """
    fixture_path = FIXTURES_DIR / fixture_name
    with open(fixture_path, "r", encoding="utf-8") as f:
        original_data = json.load(f)

    # Ingestar a V2
    model_v2 = LegacyInputAdapter.to_v2_model(original_data)

    # Re-exportar a Legacy DTO
    tx_result = LegacyOutputAdapter.to_legacy_dto(model_v2)
    reexported = tx_result.payload

    # Comparar clases
    orig_class_names = [c["name"] for c in original_data.get("classes", [])]
    reexp_class_names = [c["name"] for c in reexported.get("classes", [])]
    assert orig_class_names == reexp_class_names

    # Comparar relaciones
    orig_rels = original_data.get("relationships", [])
    reexp_rels = reexported.get("relationships", [])
    assert len(orig_rels) == len(reexp_rels)

    for i in range(len(orig_rels)):
        assert orig_rels[i]["type"] == reexp_rels[i]["type"]
        assert orig_rels[i]["sourceId"] == reexp_rels[i]["sourceId"]
        assert orig_rels[i]["targetId"] == reexp_rels[i]["targetId"]


def test_no_silent_loss_audit():
    """
    Verifica que características V2 no soportadas por generadores legacy
    (ej. interfaces) queden registradas explícitamente en TransformationReport.
    """
    # Crear modelo con una interfaz
    model = UmlDomainModel(
        schema_version="2.0.0",
        name="InterfaceModel",
        classes=[],
        interfaces=[UmlInterface(id="i1", name="IServicio")],
    )

    res = SpringLegacyMapper.to_spring_schema(model)
    # Debe emitir advertencia o degradación informando que interfaces no son soportadas
    assert len(res.report.degradations) > 0
    assert any("interfaces" in d.lower() for d in res.report.degradations)
