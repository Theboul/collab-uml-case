"""
Script de validación de tamaño y modularidad de código fuente — RULE-CODE-QUALITY.
Recorre el proyecto verificando que ningún archivo fuente exceda el límite de seguridad (1000 líneas)
y emitiendo advertencias preventivas a partir de 800 líneas.
"""

from pathlib import Path
import os
import sys

WARN_LIMIT = 800
ERROR_LIMIT = 1000

EXTENSIONS = {".py", ".ts", ".html", ".css", ".scss"}

IGNORED_PARTS = {
    "node_modules",
    "dist",
    "build",
    "coverage",
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    ".angular",
    ".pytest_cache",
    ".ruff_cache",
    ".vscode",
}

# Rutas de referencia histórica o scaffolding externo excluidas de la aplicación activa
EXCLUDED_PATHS = {
    "mobile_app_reference",
    os.path.join("front_generador_bd", "src", "services", "diagram"),
}

def main():
    root_dir = Path(__file__).resolve().parent.parent
    violations = []
    warnings = []
    checked_count = 0

    for root, dirs, files in os.walk(root_dir):
        # Poda rápida de directorios ignorados antes de recorrerlos
        dirs[:] = [d for d in dirs if d not in IGNORED_PARTS and not d.startswith(".")]

        for file_name in files:
            file_path = Path(root) / file_name
            if file_path.suffix not in EXTENSIONS:
                continue

            rel_path = file_path.relative_to(root_dir)
            rel_str = str(rel_path).replace("\\", "/")

            if any(rel_str.startswith(ex.replace("\\", "/")) for ex in EXCLUDED_PATHS):
                continue

            checked_count += 1
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = len(content.splitlines())
            except Exception:
                continue

            if lines >= ERROR_LIMIT:
                violations.append((rel_path, lines))
                print(f"[ERROR] {rel_path} -> {lines} líneas (supera límite absoluto de {ERROR_LIMIT})")
            elif lines >= WARN_LIMIT:
                warnings.append((rel_path, lines))
                print(f"[WARN]  {rel_path} -> {lines} líneas (requiere refactor preventivo antes de crecer)")

    print(f"\nResumen: {checked_count} archivos verificados.")
    if warnings:
        print(f"Advertencias ({len(warnings)} archivos >= {WARN_LIMIT} líneas):")
        for p, l in warnings:
            print(f"  - {p}: {l} líneas")

    if violations:
        print(f"\nFallo de calidad: {len(violations)} archivo(s) superan el límite de {ERROR_LIMIT} líneas.")
        sys.exit(1)

    print("\nFile-size check: PASSED.")

if __name__ == "__main__":
    main()
