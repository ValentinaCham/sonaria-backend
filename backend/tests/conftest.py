import uuid
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models.user import User
from app.security.jwt import create_access_token


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def fake_user():
    user = MagicMock(spec=User)
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def auth_token(fake_user):
    return create_access_token(str(fake_user.id))


@pytest.fixture
def client(mock_db, fake_user, auth_token):
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: fake_user
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
