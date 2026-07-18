from app.config import settings


class GeminiService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.client = None

    async def initialize(self):
        if self.api_key:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)

    async def summarize(self, context: str) -> str:
        if not self.client:
            return ""
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash", contents=f"Resume esto:\n{context}"
        )
        return response.text

    async def ask(self, question: str, context: str) -> str:
        if not self.client:
            return ""
        response = await self.client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=f"Contexto:\n{context}\n\nPregunta:\n{question}",
        )
        return response.text
