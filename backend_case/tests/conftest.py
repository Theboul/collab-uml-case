import os

import pytest
from fastapi.testclient import TestClient

# Ensure all tests run on an isolated test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_case.db"
# El backend exige JWT_SECRET al importarse; las pruebas usan uno propio.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production"


@pytest.fixture(autouse=True)
def _ensure_lifespan():
    from backend_case.app.main import app

    with TestClient(app):
        yield
