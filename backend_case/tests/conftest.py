import os

# Ensure all tests run on an isolated test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_case.db"
# El backend exige JWT_SECRET al importarse; las pruebas usan uno propio.
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-production"
