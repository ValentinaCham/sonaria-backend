import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


class TestStartConversation:
    def test_start_conversation_success(self, client):
        mock_conv_repo = MagicMock()
        fake_conv = MagicMock()
        fake_conv.id = uuid.uuid4()
        fake_conv.started_at = datetime.now(timezone.utc)
        mock_conv_repo.create.return_value = fake_conv

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.post("/conversations/start")

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert "started_at" in data


class TestEndConversation:
    def test_end_conversation_success(self, client):
        mock_conv_repo = MagicMock()
        fake_conv = MagicMock()
        fake_conv.id = uuid.uuid4()
        fake_conv.ended_at = datetime.now(timezone.utc)
        mock_conv_repo.end.return_value = fake_conv

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.post(
                f"/conversations/{fake_conv.id}/end"
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "ended_at" in data

    def test_end_conversation_not_found(self, client):
        mock_conv_repo = MagicMock()
        mock_conv_repo.end.return_value = None

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.post(
                f"/conversations/{uuid.uuid4()}/end"
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"


class TestConversationHistory:
    def test_conversation_history_success(self, client):
        mock_conv_repo = MagicMock()
        fake_conv = MagicMock()
        fake_conv.id = uuid.uuid4()
        fake_conv.started_at = datetime.now(timezone.utc)
        mock_conv_repo.get_by_user.return_value = [fake_conv]

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.get("/conversations/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]

    def test_conversation_history_empty(self, client):
        mock_conv_repo = MagicMock()
        mock_conv_repo.get_by_user.return_value = []

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.get("/conversations/history")

        assert response.status_code == 200
        assert response.json() == []


class TestConversationDetail:
    def test_conversation_detail_success(self, client):
        mock_conv_repo = MagicMock()
        mock_msg_repo = MagicMock()
        fake_conv = MagicMock()
        fake_conv.id = uuid.uuid4()
        fake_conv.title = "Test Conversation"
        fake_conv.summary = "A summary"
        fake_conv.started_at = datetime.now(timezone.utc)
        fake_conv.ended_at = None
        fake_conv.is_active = True
        fake_msg = MagicMock()
        fake_msg.id = uuid.uuid4()
        fake_msg.speaker_label = "Person A"
        fake_msg.transcription = "Hello"
        fake_msg.spoken_at = datetime.now(timezone.utc)
        fake_conv.messages = [fake_msg]
        mock_conv_repo.get_by_id.return_value = fake_conv
        mock_msg_repo.get_by_conversation.return_value = [fake_msg]

        patches = [
            patch(
                "app.routers.conversations.ConversationRepository",
                return_value=mock_conv_repo,
            ),
            patch(
                "app.routers.conversations.MessageRepository",
                return_value=mock_msg_repo,
            ),
        ]
        with patches[0], patches[1]:
            response = client.get(f"/conversations/{fake_conv.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Conversation"
        assert data["summary"] == "A summary"
        assert data["is_active"] is True
        assert len(data["messages"]) == 1
        assert data["messages"][0]["transcription"] == "Hello"

    def test_conversation_detail_not_found(self, client):
        mock_conv_repo = MagicMock()
        mock_conv_repo.get_by_id.return_value = None

        with patch(
            "app.routers.conversations.ConversationRepository",
            return_value=mock_conv_repo,
        ):
            response = client.get(f"/conversations/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Conversation not found"
