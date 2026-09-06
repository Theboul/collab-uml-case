import os
import pytest

# Ensure all tests run on an isolated test database
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_case.db"
