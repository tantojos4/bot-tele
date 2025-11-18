from fastapi.testclient import TestClient
import notify_api
import bot as bot_module

# configure secret and subscribers
notify_api.NOTIFY_API_KEY = 'secret'
bot_module._load_subscribers = lambda: {1001, 1002, 1003}

with TestClient(notify_api.app) as client:
    resp = client.post('/notify', json={'message': 'Broadcast Message'}, headers={'X-API-KEY': 'secret'})
    print('status', resp.status_code)
    try:
        print('json', resp.json())
    except Exception as e:
        print('text', resp.text)
