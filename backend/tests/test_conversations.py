import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class TestStartConversation:
    def test_start_conversation_success(self, client):
        mock_svc = MagicMock()
        fake_conv = {
            "id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc),
        }
        mock_svc.start.return_value = fake_conv

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.post("/conversations/start")

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "started_at" in data


class TestEndConversation:
    def test_end_conversation_success(self, client):
        mock_svc = MagicMock()
        fake_conv = {
            "id": str(uuid.uuid4()),
            "ended_at": datetime.now(timezone.utc),
        }
        mock_svc.end.return_value = fake_conv

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.post(f"/conversations/{uuid.uuid4()}/end")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "ended_at" in data

    def test_end_conversation_not_found(self, client):
        mock_svc = MagicMock()
        mock_svc.end.return_value = None

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.post(f"/conversations/{uuid.uuid4()}/end")

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"


class TestConversationHistory:
    def test_conversation_history_success(self, client):
        mock_svc = MagicMock()
        fake_convs = [
            {
                "id": str(uuid.uuid4()),
                "started_at": datetime.now(timezone.utc),
            }
        ]
        mock_svc.get_history.return_value = fake_convs

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.get("/conversations/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]

    def test_conversation_history_empty(self, client):
        mock_svc = MagicMock()
        mock_svc.get_history.return_value = []

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.get("/conversations/history")

        assert response.status_code == 200
        assert response.json() == []


class TestConversationDetail:
    def test_conversation_detail_success(self, client):
        mock_svc = MagicMock()
        fake_detail = {
            "id": str(uuid.uuid4()),
            "title": "Test Conversation",
            "summary": "A summary",
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "is_active": True,
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "speaker_label": "Person A",
                    "transcription": "Hello",
                    "spoken_at": datetime.now(timezone.utc),
                }
            ],
        }
        mock_svc.get_detail.return_value = fake_detail

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.get(f"/conversations/{uuid.uuid4()}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Conversation"
        assert data["summary"] == "A summary"
        assert data["is_active"] is True
        assert len(data["messages"]) == 1
        assert data["messages"][0]["transcription"] == "Hello"

    def test_conversation_detail_not_found(self, client):
        mock_svc = MagicMock()
        mock_svc.get_detail.return_value = None

        with patch(
            "app.routers.conversations.ConversationService", return_value=mock_svc
        ):
            response = client.get(f"/conversations/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"
