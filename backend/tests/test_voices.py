import uuid
from unittest.mock import MagicMock, patch


class TestRegisterVoice:
    def test_register_voice_success(self, client):
        mock_repo = MagicMock()
        fake_voice = MagicMock()
        fake_voice.id = uuid.uuid4()
        fake_voice.name = "Test Voice"
        fake_voice.is_prioritized = False
        mock_repo.create.return_value = fake_voice

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.post(
                "/voices/register", json={"name": "Test Voice"}
            )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Voice"
        assert data["is_prioritized"] is False
        assert "id" in data

    def test_register_voice_missing_name(self, client):
        response = client.post("/voices/register", json={})
        assert response.status_code == 422

    def test_register_voice_unauthorized(self, anon_client):
        response = anon_client.post(
            "/voices/register", json={"name": "Test Voice"}
        )
        assert response.status_code == 403


class TestListVoices:
    def test_list_voices_success(self, client):
        mock_repo = MagicMock()
        fake_voice = MagicMock()
        fake_voice.id = uuid.uuid4()
        fake_voice.name = "Voice 1"
        fake_voice.is_prioritized = True
        mock_repo.get_by_user.return_value = [fake_voice]

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.get("/voices")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Voice 1"
        assert data[0]["is_prioritized"] is True

    def test_list_voices_empty(self, client):
        mock_repo = MagicMock()
        mock_repo.get_by_user.return_value = []

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.get("/voices")

        assert response.status_code == 200
        assert response.json() == []


class TestUpdateVoice:
    def test_update_voice_success(self, client):
        mock_repo = MagicMock()
        fake_voice = MagicMock()
        fake_voice.id = uuid.uuid4()
        fake_voice.name = "Updated Voice"
        fake_voice.is_prioritized = True
        mock_repo.update.return_value = fake_voice

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.put(
                f"/voices/{fake_voice.id}",
                json={"name": "Updated Voice", "is_prioritized": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Voice"
        assert data["is_prioritized"] is True

    def test_update_voice_not_found(self, client):
        mock_repo = MagicMock()
        mock_repo.update.return_value = None

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.put(
                f"/voices/{uuid.uuid4()}",
                json={"name": "Ghost Voice"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Voice not found"


class TestDeleteVoice:
    def test_delete_voice_success(self, client):
        mock_repo = MagicMock()
        mock_repo.delete.return_value = True

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.delete(f"/voices/{uuid.uuid4()}")

        assert response.status_code == 204

    def test_delete_voice_not_found(self, client):
        mock_repo = MagicMock()
        mock_repo.delete.return_value = False

        with patch("app.routers.voices.VoiceRepository", return_value=mock_repo):
            response = client.delete(f"/voices/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Voice not found"
