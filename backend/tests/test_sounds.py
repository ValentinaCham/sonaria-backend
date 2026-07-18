import uuid
from unittest.mock import MagicMock, patch


class TestListSounds:
    def test_list_sounds_success(self, client):
        mock_sound_repo = MagicMock()
        fake_sound = MagicMock()
        fake_sound.id = uuid.uuid4()
        fake_sound.category = "doorbell"
        fake_sound.custom_name = "Front Door"
        fake_sound.is_active = True
        mock_sound_repo.get_by_user.return_value = [fake_sound]

        with patch(
            "app.routers.sounds.SoundRepository", return_value=mock_sound_repo
        ):
            response = client.get("/sounds")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["category"] == "doorbell"
        assert data[0]["custom_name"] == "Front Door"
        assert data[0]["is_active"] is True

    def test_list_sounds_empty(self, client):
        mock_sound_repo = MagicMock()
        mock_event_repo = MagicMock()
        mock_sound_repo.get_by_user.return_value = []

        with (
            patch(
                "app.routers.sounds.SoundRepository",
                return_value=mock_sound_repo,
            ),
            patch(
                "app.routers.sounds.EventRepository",
                return_value=mock_event_repo,
            ),
        ):
            response = client.get("/sounds")

        assert response.status_code == 200
        assert response.json() == []


class TestConfigSound:
    def test_config_sound_create(self, client):
        mock_sound_repo = MagicMock()
        mock_event_repo = MagicMock()
        fake_sound = MagicMock()
        fake_sound.id = uuid.uuid4()
        fake_sound.category = "alarm"
        fake_sound.custom_name = "Fire Alarm"
        fake_sound.is_active = True
        mock_sound_repo.create_or_update.return_value = fake_sound

        with (
            patch(
                "app.routers.sounds.SoundRepository",
                return_value=mock_sound_repo,
            ),
            patch(
                "app.routers.sounds.EventRepository",
                return_value=mock_event_repo,
            ),
        ):
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
        mock_sound_repo = MagicMock()
        mock_event_repo = MagicMock()
        mock_sound_repo.create_or_update.side_effect = ValueError(
            "Invalid category"
        )

        with (
            patch(
                "app.routers.sounds.SoundRepository",
                return_value=mock_sound_repo,
            ),
            patch(
                "app.routers.sounds.EventRepository",
                return_value=mock_event_repo,
            ),
        ):
            response = client.post(
                "/sounds/config",
                json={
                    "category": "invalid_category",
                    "custom_name": "Test",
                },
            )

        assert response.status_code == 500
