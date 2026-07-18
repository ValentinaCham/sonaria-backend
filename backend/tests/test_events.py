import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class TestListEvents:
    def test_list_events_success(self, client):
        mock_svc = MagicMock()
        fake_events = [
            {
                "id": str(uuid.uuid4()),
                "context_message": "Doorbell detected",
                "detected_at": datetime.now(timezone.utc),
                "is_notified": False,
            }
        ]
        mock_svc.list_events.return_value = fake_events

        with patch("app.routers.events.SoundService", return_value=mock_svc):
            response = client.get("/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["context_message"] == "Doorbell detected"
        assert data[0]["is_notified"] is False
        assert "detected_at" in data[0]

    def test_list_events_empty(self, client):
        mock_svc = MagicMock()
        mock_svc.list_events.return_value = []

        with patch("app.routers.events.SoundService", return_value=mock_svc):
            response = client.get("/events")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_events_unauthorized(self, anon_client):
        response = anon_client.get("/events")
        assert response.status_code in (401, 403)
