import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.security.jwt import create_access_token


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def fake_user_id():
    return str(uuid.uuid4())


@pytest.fixture
def auth_token(fake_user_id):
    return create_access_token(fake_user_id)


@pytest.fixture
def client(mock_db, fake_user_id, auth_token):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=fake_user_id, email="test@example.com"
    )
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {auth_token}"}
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()
