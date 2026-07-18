import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class TestListEvents:
    def test_list_events_success(self, client):
        mock_sound_repo = MagicMock()
        mock_event_repo = MagicMock()
        fake_event = MagicMock()
        fake_event.id = uuid.uuid4()
        fake_event.context_message = "Doorbell detected"
        fake_event.detected_at = datetime.now(timezone.utc)
        fake_event.is_notified = False
        mock_event_repo.get_by_user.return_value = [fake_event]

        with (
            patch(
                "app.routers.events.SoundRepository",
                return_value=mock_sound_repo,
            ),
            patch(
                "app.routers.events.EventRepository",
                return_value=mock_event_repo,
            ),
        ):
            response = client.get("/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["context_message"] == "Doorbell detected"
        assert data[0]["is_notified"] is False
        assert "detected_at" in data[0]

    def test_list_events_empty(self, client):
        mock_sound_repo = MagicMock()
        mock_event_repo = MagicMock()
        mock_event_repo.get_by_user.return_value = []

        with (
            patch(
                "app.routers.events.SoundRepository",
                return_value=mock_sound_repo,
            ),
            patch(
                "app.routers.events.EventRepository",
                return_value=mock_event_repo,
            ),
        ):
            response = client.get("/events")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_events_unauthorized(self, anon_client):
        response = anon_client.get("/events")
        assert response.status_code == 403
