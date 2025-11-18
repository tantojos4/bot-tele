import asyncio
import os
import pytest
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

import bot as bot_module
import notify_api


@pytest.mark.asyncio
async def test_notify_broadcast(monkeypatch):
    # add env key to module
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"

    # Mock subscribers map (id -> metadata)
    async def _fake_subs_map_1():
        return {
            1001: {"first_name": "Alice", "last_name": "Aldo", "username": "alice"},
            1002: {"first_name": "Bob", "last_name": "Barker", "username": "bob"},
            1003: {"first_name": "Carol", "last_name": "Carter", "username": "carol"},
        }
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_1)

    called = []

    async def fake_send_message(*args, **kwargs):
        # accept either positional or keyword args
        chat_id = kwargs.get('chat_id') if 'chat_id' in kwargs else (args[0] if args else None)
        text = kwargs.get('text') if 'text' in kwargs else (args[1] if len(args) > 1 else None)
        called.append((chat_id, text))

    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Broadcast Message"}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 3
        assert len(called) == 3


@pytest.mark.asyncio
async def test_notify_chat_id(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"

    called = []

    async def fake_send_message(chat_id, text):
        called.append((chat_id, text))

    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Direct", "chat_id": 999}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 1
    assert called[0][0] == 999


@pytest.mark.asyncio
async def test_notify_by_username(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"
    called = []

    async def fake_send_message(*args, **kwargs):
        chat_id = kwargs.get('chat_id') if 'chat_id' in kwargs else (args[0] if args else None)
        text = kwargs.get('text') if 'text' in kwargs else (args[1] if len(args) > 1 else None)
        called.append((chat_id, text))

    async def _fake_subs_map_2():
        return {
            2001: {"first_name": "Eve", "last_name": "Evans", "username": "eve"},
            2002: {"first_name": "Mallory", "last_name": "Mills", "username": "mallory"},
        }
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_2)
    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Hello User", "username": "eve"}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 1
        assert called[0][0] == 2001


@pytest.mark.asyncio
async def test_notify_by_first_name(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"
    called = []

    async def fake_send_message(*args, **kwargs):
        chat_id = kwargs.get('chat_id') if 'chat_id' in kwargs else (args[0] if args else None)
        text = kwargs.get('text') if 'text' in kwargs else (args[1] if len(args) > 1 else None)
        called.append((chat_id, text))

    async def _fake_subs_map_3():
        return {
            3001: {"first_name": "John", "last_name": "Johnson", "username": "john"},
            3002: {"first_name": "Johnny", "last_name": "Johnson", "username": "johnny"},
            3003: {"first_name": "Alice", "last_name": "Anderson", "username": "alice"},
        }
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_3)
    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Hello John", "first_name": "john"}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        # john matches both John and Johnny; case-insensitive substring
        assert data["sent"] == 2


@pytest.mark.asyncio
async def test_notify_by_last_name(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"
    called = []

    async def fake_send_message(*args, **kwargs):
        chat_id = kwargs.get('chat_id') if 'chat_id' in kwargs else (args[0] if args else None)
        text = kwargs.get('text') if 'text' in kwargs else (args[1] if len(args) > 1 else None)
        called.append((chat_id, text))

    async def _fake_subs_map_4():
        return {
            4001: {"first_name": "John", "last_name": "Smith", "username": "john"},
            4002: {"first_name": "Mary", "last_name": "Smith", "username": "mary"},
            4003: {"first_name": "Alice", "last_name": "Jones", "username": "alice"},
        }
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_4)
    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Hello Smith", "last_name": "smith"}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 2


def test_notify_by_nip(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"
    called = []

    async def fake_send_message(*args, **kwargs):
        chat_id = kwargs.get('chat_id') if 'chat_id' in kwargs else (args[0] if args else None)
        text = kwargs.get('text') if 'text' in kwargs else (args[1] if len(args) > 1 else None)
        called.append((chat_id, text))

    async def _fake_subs_map_6():
        return {
            9001: {"first_name": "A", "last_name": "A", "username": "a", "nip": "NIP123"},
            9002: {"first_name": "B", "last_name": "B", "username": "b", "nip": "NIP999"},
        }
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_6)
    monkeypatch.setattr(notify_api, "bot", type("X", (), {"send_message": staticmethod(fake_send_message)}))

    with TestClient(notify_api.app) as client:
        resp = client.post("/notify", json={"message": "Hello NIP", "nip": "NIP123"}, headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sent"] == 1

def test_get_subscribers(monkeypatch):
    monkeypatch.setenv("NOTIFY_API_KEY", "secret")
    notify_api.NOTIFY_API_KEY = "secret"
    async def _fake_subs_map_5():
        return {4001: {"first_name": "AA", "last_name": "AA-L", "username": "aa"}}
    monkeypatch.setattr(notify_api, "_load_subscribers_map", _fake_subs_map_5)
    with TestClient(notify_api.app) as client:
        resp = client.get("/subscribers", headers={"X-API-KEY": "secret"})
        assert resp.status_code == 200
        data = resp.json()
        assert "4001" in data
        assert data['4001'].get('last_name') == 'AA-L'


def test_get_subscribers_legacy_list(tmp_path, monkeypatch):
    # Arrange: write legacy list to file
    subs_file = tmp_path / "legacy_subs.json"
    subs_file.write_text('[1, 1410681826]', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'

    with TestClient(notify_api.app) as client:
        resp = client.get('/subscribers', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        # keys should be strings
        assert '1' in data
        assert '1410681826' in data
        # legacy entries will have last_name set to None after migration
        assert data['1'].get('last_name') is None


def test_migrate_dict_adds_last_name(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_migr.json"
    # write an existing dict that misses 'last_name'
    subs_file.write_text('{"1410681826": {"first_name": "Yusup", "username": "uwcup46", "subscribed_at": "2025-11-18T03:46:45.489811+00:00"}}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'

    with TestClient(notify_api.app) as client:
        resp = client.get('/subscribers', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert '1410681826' in data
        assert data['1410681826'].get('last_name') is None
    # Check that the file on disk now includes the key 'last_name'
    content = subs_file.read_text(encoding='utf-8')
    assert 'last_name' in content


def test_put_update_subscriber_existing(tmp_path, monkeypatch):
    # setup legacy or map file
    subs_file = tmp_path / "subs_map.json"
    subs_map = {"1410681826": {"first_name": None, "last_name": None, "username": None, "subscribed_at": "2025-11-18T03:08:47.582244+00:00"}}
    subs_file.write_text(json.dumps(subs_map), encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/1410681826', json={'first_name': 'Eko', 'username': 'eko'}, headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['1410681826']['first_name'] == 'Eko'
        assert data['1410681826']['username'] == 'eko'
        assert data['1410681826'].get('last_name') is None


def test_put_update_subscriber_create(tmp_path, monkeypatch):
    # start with empty file
    subs_file = tmp_path / "subs_map2.json"
    subs_file.write_text('{}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/22222', json={'first_name': 'Zoe', 'username': 'zoe'}, headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['22222']['first_name'] == 'Zoe'
        assert data['22222']['username'] == 'zoe'
        assert data['22222'].get('last_name') is None


    def test_put_update_subscriber_last_name(tmp_path, monkeypatch):
        subs_file = tmp_path / "subs_map_last.json"
        subs_file.write_text('{}', encoding='utf-8')
        monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
        monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
        notify_api.NOTIFY_API_KEY = 'secret'
        with TestClient(notify_api.app) as client:
            resp = client.put('/subscribers/5555', json={'last_name': 'Family'}, headers={'X-API-KEY': 'secret'})
            assert resp.status_code == 200
            data = resp.json()
            assert data['5555']['last_name'] == 'Family'


def test_put_update_subscriber_unauthorized(tmp_path, monkeypatch):
    # require API key
    subs_file = tmp_path / "subs_map3.json"
    subs_file.write_text('{}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    # API key required but we don't provide it in the request header
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/3333', json={'first_name': 'X'}, headers={})
        assert resp.status_code == 401


def test_put_update_subscriber_set_nip(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_map_nip.json"
    subs_map = {"1410681826": {"first_name": None, "last_name": None, "username": None, "subscribed_at": "2025-11-18T03:08:47.582244+00:00"}}
    subs_file.write_text(json.dumps(subs_map), encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/1410681826', json={'nip': '123456789012345'}, headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['1410681826']['nip'] == '123456789012345'


def test_put_update_subscriber_truncates_nip(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_map_nip2.json"
    subs_file.write_text('{}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    long_nip = 'X' * 25
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/3333', json={'nip': long_nip}, headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        # Should be truncated to 18 characters
        assert len(data['3333']['nip']) == 18


def test_put_rejects_raw_telegram_update(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_raw.json"
    subs_file.write_text('{}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    raw_telegram_payload = {
        "update_id": 1,
        "message": {
            "message_id": 26,
            "from": {"id": 1410681826, "is_bot": False, "first_name": "Yusup", "username": "uwcup46"},
            "chat": {"id": 1410681826, "first_name": "Yusup", "username": "uwcup46", "type": "private"},
            "date": 1763436295,
            "text": "/start",
        }
    }
    with TestClient(notify_api.app) as client:
        resp = client.put('/subscribers/1410681826', json=raw_telegram_payload, headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 422


def test_notify_rejects_raw_telegram_message(monkeypatch):
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    raw_telegram_msg = {
        "message": {
            "message_id": 26,
            "from": {"id": 1410681826, "is_bot": False, "first_name": "Yusup"},
            "chat": {"id": 1410681826, "type": "private"},
            "date": 1763436295,
            "text": "/start",
        }
    }
    with TestClient(notify_api.app) as client:
        resp = client.post('/notify', json=raw_telegram_msg, headers={'X-API-KEY': 'secret'})
        # should be 422 because NotifyRequest expects 'message' string not object
        assert resp.status_code == 422


def test_sync_subscriber_fetch_and_update(tmp_path, monkeypatch):
    # Prepare file with a bare entry
    subs_file = tmp_path / "subs_sync.json"
    subs_file.write_text('{"1410681826": {"first_name": null, "last_name": null, "username": null}}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'

    class FakeChat:
        def __init__(self):
            self.first_name = 'Updated'
            self.last_name = 'UpdatedLast'
            self.username = 'updated_user'

    class FakeBot:
        async def get_chat(self, cid):
            return FakeChat()

    monkeypatch.setattr(notify_api, 'get_bot', lambda: FakeBot())

    with TestClient(notify_api.app) as client:
        resp = client.post('/subscribers/1410681826/sync', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
    assert data['1410681826']['first_name'] == 'Updated'
    assert data['1410681826']['last_name'] == 'UpdatedLast'
    assert data['1410681826']['username'] == 'updated_user'


def test_sync_all_subscribers(tmp_path, monkeypatch):
    # prepare file with multiple entries
    subs_file = tmp_path / "subs_sync_all.json"
    subs_file.write_text('{"1001": {"first_name": null, "last_name": null, "username": null}, "1002": {"first_name": null, "last_name": null, "username": null}}', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'

    class FakeChat:
        def __init__(self, first):
            self.first_name = first
            self.last_name = f"{first}Last"
            self.username = first.lower()

    class FakeBot:
        async def get_chat(self, cid):
            return FakeChat(f'user{cid}')

    monkeypatch.setattr(notify_api, 'get_bot', lambda: FakeBot())

    with TestClient(notify_api.app) as client:
        resp = client.post('/subscribers/sync', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data['updated'] == 2


def test_empty_subscribers_file_returns_empty(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_empty.json"
    subs_file.write_text('', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.get('/subscribers', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {}


def test_invalid_subscribers_file_backed_up(tmp_path, monkeypatch):
    subs_file = tmp_path / "subs_invalid.json"
    subs_file.write_text('not-a-json', encoding='utf-8')
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(subs_file))
    monkeypatch.setenv('NOTIFY_API_KEY', 'secret')
    notify_api.NOTIFY_API_KEY = 'secret'
    with TestClient(notify_api.app) as client:
        resp = client.get('/subscribers', headers={'X-API-KEY': 'secret'})
        assert resp.status_code == 200
        data = resp.json()
        assert data == {}
    # After request, the invalid file should be backed up and replaced by {}
    assert subs_file.exists()
    content = subs_file.read_text(encoding='utf-8')
    assert content.strip() != 'not-a-json'