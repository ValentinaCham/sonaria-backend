from app.config import settings


class DeepgramService:
    def __init__(self):
        self.api_key = settings.DEEPGRAM_API_KEY
        self.client = None

    async def initialize(self):
        if self.api_key:
            from deepgram import DeepgramClient
            self.client = DeepgramClient(self.api_key)

    async def transcribe(self, audio_bytes: bytes) -> dict:
        if not self.client:
            return {"text": "", "speakers": []}
        result = await self.client.transcription.prerecorded(
            {"buffer": audio_bytes, "mimetype": "audio/webm"},
            {"model": "nova-2", "diarize": True},
        )
        return self._parse(result)

    def _parse(self, result) -> dict:
        if not result or not result.results:
            return {"text": "", "speakers": []}
        channels = result.results.channels
        if not channels:
            return {"text": "", "speakers": []}
        words = channels[0].alternatives[0].words
        speakers = {}
        full_text = []
        for w in words:
            spk = getattr(w, "speaker", 0)
            if spk not in speakers:
                speakers[spk] = {"label": f"Speaker {spk}", "words": []}
            speakers[spk]["words"].append(w.word)
            full_text.append(w.word)
        return {
            "text": " ".join(full_text),
            "speakers": [
                {"label": s["label"], "text": " ".join(s["words"])}
                for s in speakers.values()
            ],
        }
