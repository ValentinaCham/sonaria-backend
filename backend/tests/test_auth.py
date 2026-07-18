import uuid
from unittest.mock import MagicMock, patch

from app.security.password import hash_password


class TestRegister:
    def test_register_success(self, anon_client):
        mock_repo = MagicMock()
        mock_repo.get_by_email.return_value = None
        fake_id = uuid.uuid4()
        mock_repo.create.return_value = MagicMock(id=fake_id)

        with patch("app.routers.auth.UserRepository", return_value=mock_repo):
            response = anon_client.post(
                "/auth/register",
                json={"email": "new@example.com", "password": "password123"},
            )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, anon_client):
        mock_repo = MagicMock()
        existing_user = MagicMock()
        existing_user.email = "existing@example.com"
        mock_repo.get_by_email.return_value = existing_user

        with patch("app.routers.auth.UserRepository", return_value=mock_repo):
            response = anon_client.post(
                "/auth/register",
                json={"email": "existing@example.com", "password": "password123"},
            )

        assert response.status_code == 409
        assert response.json()["detail"] == "Email already registered"

    def test_register_invalid_email(self, anon_client):
        response = anon_client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "password123"},
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, anon_client):
        mock_repo = MagicMock()
        hashed = hash_password("password123")
        fake_id = uuid.uuid4()
        mock_repo.get_by_email.return_value = MagicMock(
            password_hash=hashed, id=fake_id
        )

        with patch("app.routers.auth.UserRepository", return_value=mock_repo):
            response = anon_client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "password123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, anon_client):
        mock_repo = MagicMock()
        hashed = hash_password("correct-password")
        mock_repo.get_by_email.return_value = MagicMock(password_hash=hashed)

        with patch("app.routers.auth.UserRepository", return_value=mock_repo):
            response = anon_client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "wrong-password"},
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_login_user_not_found(self, anon_client):
        mock_repo = MagicMock()
        mock_repo.get_by_email.return_value = None

        with patch("app.routers.auth.UserRepository", return_value=mock_repo):
            response = anon_client.post(
                "/auth/login",
                json={
                    "email": "nonexistent@example.com",
                    "password": "password123",
                },
            )

        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"


class TestMe:
    def test_me_success(self, client):
        response = client.get("/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data

    def test_me_unauthorized(self, anon_client):
        response = anon_client.get("/auth/me")
        assert response.status_code in (401, 403)
