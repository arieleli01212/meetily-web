"""Shared test fixtures."""
import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.main import app, get_db


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "api.db"))


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
