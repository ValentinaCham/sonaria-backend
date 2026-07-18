from assemblyai.streaming.v3 import StreamingClient
print([m for m in dir(StreamingClient) if not m.startswith('_')])
