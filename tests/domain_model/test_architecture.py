"""
Test de arquitectura: `core/uml_domain` debe seguir siendo puro.

Este test es la versión ejecutable de la regla "core/uml_domain no depende
de frameworks" — si alguien (humano o agente de IA) agrega un import
prohibido, el build falla en vez de depender de que alguien lo note en
una revisión manual.
"""

import ast
from pathlib import Path

FRAMEWORKS_PROHIBIDOS = {
    "fastapi",
    "sqlalchemy",
    "pydantic",
    "starlette",
    "django",
}

DOMAIN_ROOT = Path(__file__).resolve().parent.parent.parent / "core" / "uml_domain"


def _imports_en(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modulos = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modulos.add(node.module.split(".")[0])
    return modulos


def test_core_uml_domain_no_importa_frameworks():
    archivos_py = [
        p for p in DOMAIN_ROOT.rglob("*.py")
        if "tests" not in p.parts and p.name != "__init__.py"
    ]
    assert archivos_py, f"No se encontraron archivos .py en {DOMAIN_ROOT} para verificar."

    violaciones = {}
    for archivo in archivos_py:
        prohibidos_encontrados = _imports_en(archivo) & FRAMEWORKS_PROHIBIDOS
        if prohibidos_encontrados:
            violaciones[str(archivo.relative_to(DOMAIN_ROOT))] = prohibidos_encontrados

    assert not violaciones, (
        "core/uml_domain importa frameworks prohibidos "
        "(rompe el aislamiento del dominio):\n"
        f"{violaciones}"
    )
