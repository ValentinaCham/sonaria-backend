class YAMNetService:
    def __init__(self):
        self.model = None

    async def initialize(self):
        pass

    async def classify(self, audio_bytes: bytes) -> list[dict]:
        return []
