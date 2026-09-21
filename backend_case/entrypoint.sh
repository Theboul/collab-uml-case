#!/bin/sh
set -e

# Inicialización determinística de la base de datos (un solo proceso antes de lanzar workers)
echo "[entrypoint] Verificando esquemas y tablas de base de datos..."
python -c "import asyncio; from app.shared.db.base import init_db; from app.legacy.database import init_legacy_db; asyncio.run(init_db()); asyncio.run(init_legacy_db())" || echo "[entrypoint] Advertencia durante init_db, continuando..."

echo "[entrypoint] Iniciando proceso principal..."
exec "$@"
