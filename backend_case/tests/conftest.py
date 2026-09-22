import os

import pytest
from fastapi.testclient import TestClient

# Ensure all tests run on an isolated test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_case.db"
# El backend exige JWT_SECRET al importarse; las pruebas usan uno propio.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production"

# DIAGNOSTICO TEMPORAL: SQLite no aplica FKs por defecto (a diferencia de Postgres, usado en
# docker-compose), así que una violación de FK puede pasar en silencio en pytest y solo
# explotar en producción (caso real: join_canvas con "anonymous-user", CU2). Se activa acá
# para ver si hay otros casos de la misma familia escondidos en la suite actual.
from sqlalchemy import event  # noqa: E402

from backend_case.app.shared.db import base as _db_base  # noqa: E402


@event.listens_for(_db_base.engine.sync_engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
    if "sqlite" in str(_db_base.engine.url):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")


@pytest.fixture(autouse=True)
def _ensure_lifespan():
    from backend_case.app.main import app

    with TestClient(app):
        yield
