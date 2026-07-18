import uuid
from unittest.mock import MagicMock, patch


class TestListSounds:
    def test_list_sounds_success(self, client):
        mock_svc = MagicMock()
        fake_sounds = [
            {
                "id": str(uuid.uuid4()),
                "category": "doorbell",
                "custom_name": "Front Door",
                "is_active": True,
            }
        ]
        mock_svc.list_sounds.return_value = fake_sounds

        with patch("app.routers.sounds.SoundService", return_value=mock_svc):
            response = client.get("/sounds")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "doorbell"
        assert data[0]["custom_name"] == "Front Door"
        assert data[0]["is_active"] is True

    def test_list_sounds_empty(self, client):
        mock_svc = MagicMock()
        mock_svc.list_sounds.return_value = []

        with patch("app.routers.sounds.SoundService", return_value=mock_svc):
            response = client.get("/sounds")

        assert response.status_code == 200
        assert response.json() == []


class TestConfigSound:
    def test_config_sound_create(self, client):
        mock_svc = MagicMock()
        fake_sound = {
            "id": str(uuid.uuid4()),
            "category": "alarm",
            "custom_name": "Fire Alarm",
            "is_active": True,
        }
        mock_svc.config.return_value = fake_sound

        with patch("app.routers.sounds.SoundService", return_value=mock_svc):
            response = client.post(
                "/sounds/config",
                json={
                    "category": "alarm",
                    "custom_name": "Fire Alarm",
                    "is_active": True,
                },
            )

        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "alarm"
        assert data["custom_name"] == "Fire Alarm"
        assert data["is_active"] is True

    def test_config_sound_invalid_category(self, client):
        response = client.post(
            "/sounds/config",
            json={
                "category": "invalid_category",
                "custom_name": "Test",
            },
        )

        assert response.status_code == 422

    def test_config_sound_missing_category(self, client):
        response = client.post(
            "/sounds/config",
            json={"custom_name": "Test"},
        )
        assert response.status_code == 422
