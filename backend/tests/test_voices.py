import uuid
from unittest.mock import MagicMock, patch


class TestRegisterVoice:
    def test_register_voice_success(self, client):
        mock_svc = MagicMock()
        fake_voice = {
            "id": str(uuid.uuid4()),
            "name": "Test Voice",
            "is_prioritized": False,
        }
        mock_svc.register.return_value = fake_voice

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.post("/voices/register", json={"name": "Test Voice"})

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Voice"
        assert data["is_prioritized"] is False
        assert "id" in data

    def test_register_voice_missing_name(self, client):
        response = client.post("/voices/register", json={})
        assert response.status_code == 422

    def test_register_voice_unauthorized(self, anon_client):
        response = anon_client.post("/voices/register", json={"name": "Test Voice"})
        assert response.status_code == 403


class TestListVoices:
    def test_list_voices_success(self, client):
        mock_svc = MagicMock()
        fake_voices = [
            {
                "id": str(uuid.uuid4()),
                "name": "Voice 1",
                "is_prioritized": True,
            }
        ]
        mock_svc.list_by_user.return_value = fake_voices

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.get("/voices")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Voice 1"
        assert data[0]["is_prioritized"] is True

    def test_list_voices_empty(self, client):
        mock_svc = MagicMock()
        mock_svc.list_by_user.return_value = []

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.get("/voices")

        assert response.status_code == 200
        assert response.json() == []


class TestUpdateVoice:
    def test_update_voice_success(self, client):
        mock_svc = MagicMock()
        fake_voice = {
            "id": str(uuid.uuid4()),
            "name": "Updated Voice",
            "is_prioritized": True,
        }
        mock_svc.update.return_value = fake_voice

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.put(
                f"/voices/{uuid.uuid4()}",
                json={"name": "Updated Voice", "is_prioritized": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Voice"
        assert data["is_prioritized"] is True

    def test_update_voice_not_found(self, client):
        mock_svc = MagicMock()
        mock_svc.update.return_value = None

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.put(
                f"/voices/{uuid.uuid4()}",
                json={"name": "Ghost Voice"},
            )

        assert response.status_code == 404
        assert response.json()["detail"] == "Voice not found"


class TestDeleteVoice:
    def test_delete_voice_success(self, client):
        mock_svc = MagicMock()
        mock_svc.delete.return_value = True

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.delete(f"/voices/{uuid.uuid4()}")

        assert response.status_code == 204

    def test_delete_voice_not_found(self, client):
        mock_svc = MagicMock()
        mock_svc.delete.return_value = False

        with patch("app.routers.voices.VoiceService", return_value=mock_svc):
            response = client.delete(f"/voices/{uuid.uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Voice not found"
