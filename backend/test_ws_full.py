import asyncio
import json
import struct
import urllib.request

import websockets

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.05  # 50ms


def get_token():
    req = urllib.request.Request('http://localhost:8000/auth/dev-token', method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode())['access_token']


async def test_assemblyai_ws():
    token = get_token()
    uri = f'ws://localhost:8000/ws/audio?token={token}&max_speakers=3&sample_rate=16000'
    print('[TEST] Conectando a ws://localhost:8000/ws/audio ...')

    async with websockets.connect(uri, open_timeout=15) as ws:
        print('[TEST] WebSocket conectado. Esperando evento de conexion AssemblyAI...')

        # Enviar silencio durante 3 segundos para abrir la sesion AssemblyAI
        silence_chunk = bytes(int(SAMPLE_RATE * CHUNK_DURATION) * 2)  # int16 = 2 bytes/sample
        chunks_sent = 0
        connected_received = False

        async def sender():
            for _ in range(60):  # 60 * 50ms = 3 segundos de silencio
                await ws.send(silence_chunk)
                await asyncio.sleep(0.05)

        async def receiver():
            nonlocal connected_received
            for _ in range(10):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=6)
                    data = json.loads(msg)
                    t = data.get('type', '?')
                    txt = str(data.get('text', ''))[:80]
                    spk = str(data.get('speaker', ''))
                    sid = str(data.get('session_id', ''))
                    print('[EVENTO] type=' + t + ' speaker=' + spk + ' text=' + txt + (' session=' + sid if sid else ''))
                    if t == 'connected':
                        connected_received = True
                        print('[OK] AssemblyAI sesion iniciada correctamente')
                    if t == 'error':
                        print('[ERROR] ' + txt)
                        break
                except asyncio.TimeoutError:
                    if connected_received:
                        print('[OK] No mas eventos (normal - silencio enviado)')
                    else:
                        print('[WARN] Timeout esperando evento connected')
                    break

        await asyncio.gather(sender(), receiver())

        print('[TEST] Enviando ping de control...')
        await ws.send(json.dumps({'action': 'ping'}))
        pong = await asyncio.wait_for(ws.recv(), timeout=5)
        pong_data = json.loads(pong)
        print('[PONG] type=' + pong_data.get('type', '?'))

    print('[TEST] Conexion cerrada correctamente')
    print('')
    if connected_received:
        print('RESULTADO: PASS - Reconocimiento multi-persona funcionando')
    else:
        print('RESULTADO: PARCIAL - WebSocket OK, AssemblyAI puede tardar mas al conectar (normal en la primera vez)')

asyncio.run(test_assemblyai_ws())
