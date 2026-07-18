import asyncio, json, urllib.request
import numpy as np
import websockets


def tone(f, s, sr=16000):
    t = np.arange(int(sr * s)) / sr
    x = 0.3 * np.sin(2 * np.pi * f * t) + 0.12 * np.sin(2 * np.pi * 2 * f * t)
    return (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()


async def main():
    req = urllib.request.Request("http://127.0.0.1:8000/auth/dev-token", method="POST")
    token = json.loads(urllib.request.urlopen(req).read().decode())["access_token"]
    url = f"ws://127.0.0.1:8000/ws/audio?token={token}&max_speakers=2&sample_rate=16000&clean=true&analyze=true"
    async with websockets.connect(url, max_size=None) as ws:
        types = {}
        va = []

        async def sender():
            for _ in range(6):
                await ws.send(tone(130, 0.25))
                await asyncio.sleep(0.05)
            for _ in range(6):
                await ws.send(tone(240, 0.25))
                await asyncio.sleep(0.05)

        st = asyncio.create_task(sender())
        try:
            while True:
                data = json.loads(await asyncio.wait_for(ws.recv(), timeout=4))
                t = data.get("type")
                types[t] = types.get(t, 0) + 1
                if t == "voice_analysis":
                    va.append(data)
                if t == "error":
                    print("ERROR:", data.get("text"))
                    break
        except asyncio.TimeoutError:
            pass
        st.cancel()
        print("tipos:", types)
        if va:
            speech = [e for e in va if e["is_speech"]]
            print("voice_analysis:", len(va), "| con voz:", len(speech),
                  "| mel_len:", len(va[0]["mel"]))
            print("voice_ids:", sorted(set(e["voice_id"] for e in speech)))
            print("pitches:", sorted(set(e["pitch_hz"] for e in speech)))
        print("OK" if va else "NO_VA")


asyncio.run(main())
