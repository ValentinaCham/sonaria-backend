from assemblyai.streaming.v3 import StreamingClient, StreamingClientOptions, StreamingParameters
from app.config import settings

client = StreamingClient(StreamingClientOptions(api_key=settings.ASSEMBLYAI_API_KEY))
try:
    print("Connecting...")
    client.connect(StreamingParameters(
        speech_model="universal-3-5-pro",
        sample_rate=16000,
        language_codes=["es"],
        speaker_labels=True,
        max_speakers=5,
        format_turns=True,
    ))
    print("Connected successfully!")
    client.disconnect()
except Exception as e:
    print(f"Error: {e}")
