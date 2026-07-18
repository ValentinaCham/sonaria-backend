from app.services.ai.gemini_service import GeminiService


class SummaryService:
    def __init__(self, gemini: GeminiService):
        self.gemini = gemini

    async def summarize_conversation(self, transcript: str) -> str:
        return await self.gemini.summarize(transcript)

    async def ask_about_conversation(self, question: str, context: str) -> str:
        return await self.gemini.ask(question, context)
