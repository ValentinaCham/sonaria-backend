import asyncio
import json
import urllib.request

import websockets


def get_token():
    req = urllib.request.Request('http://localhost:8000/auth/dev-token', method='POST')
    return json.loads(urllib.request.urlopen(req).read().decode())['access_token']


async def test():
    token = get_token()
    uri = f'ws://localhost:8000/ws/audio?token={token}&max_speakers=3&sample_rate=16000'
    print('Conectando al WebSocket...')
    try:
        async with websockets.connect(uri, open_timeout=10) as ws:
            print('Conectado. Enviando ping...')
            await ws.send(json.dumps({'action': 'ping'}))
            for _ in range(5):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=8)
                    data = json.loads(msg)
                    t = data.get('type', '?')
                    txt = str(data.get('text', ''))[:60]
                    print('Recibido type=' + t + ' text=' + txt)
                    if t == 'pong':
                        print('PONG OK - WebSocket funciona correctamente')
                        break
                    if t == 'connected':
                        print('CONNECTED OK - AssemblyAI sesion iniciada: ' + str(data.get('session_id', '')))
                        await ws.send(json.dumps({'action': 'ping'}))
                except asyncio.TimeoutError:
                    print('Timeout esperando mensaje')
                    break
    except Exception as e:
        print('Error: ' + str(e))


asyncio.run(test())
