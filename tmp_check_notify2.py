from fastapi.testclient import TestClient
import notify_api
import bot as bot_module

# configure
notify_api.NOTIFY_API_KEY = 'secret'
bot_module._load_subscribers = lambda: {1001, 1002, 1003}

called = []
async def fake_sm(cid, text):
    called.append((cid, text))

notify_api.bot = type('X', (), {'send_message': staticmethod(fake_sm)})

with TestClient(notify_api.app) as client:
    r = client.post('/notify', json={'message': 'Broadcast Message'}, headers={'X-API-KEY': 'secret'})
    print('status', r.status_code)
    print('json', r.json())
    print('called', called)
