import asyncio
import os
import pytest

from telegram import Message, User, Chat
from telegram.ext import ContextTypes

import bot

@pytest.mark.asyncio
async def test_start_and_help_handlers(caplog, tmp_path, monkeypatch):
    # Build simple dummy Update with minimal fields for message.reply_text
    class DummyMessage:
        def __init__(self):
            self.text = ''
            self.chat = Chat(id=1, type='private')
            self.from_user = User(id=1, is_bot=False, first_name='Test', last_name='Tester')
            self.replies = []

        async def reply_text(self, text):
            self.replies.append(text)
            return text

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()

    # Use a temporary subscribers file for testing
    subs_file = tmp_path / "subscribers.json"
    monkeypatch.setenv("SUBSCRIBERS_FILE", str(subs_file))
    monkeypatch.setenv("FOLLOWUP_DELAY", "0")

    update = DummyUpdate()
    context = None  # not used by our handlers

    # Capture Info logs
    import logging
    caplog.set_level(logging.INFO)

    # Call start handler
    await bot.start(update, context)
    assert update.message.replies[0] == "Halo! Selamat datang di bot saya."
    assert "Received /start" in caplog.text

    # Call help handler
    update = DummyUpdate()
    await bot.help_command(update, context)
    assert update.message.replies[0] == "Gunakan /start untuk memulai bot."
    assert "Received /help" in caplog.text

    # Call haysay handler
    update = DummyUpdate()
    await bot.haysay(update, context)
    assert update.message.replies[0] == "hay say"
    assert "Received /haysay" in caplog.text

    # Verify subscribers file was written with chat id 1
    import json
    with open(subs_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        # keys saved as strings
        assert '1' in data
    assert data['1'].get('first_name') == 'Test'
    assert data['1'].get('last_name') == 'Tester'


def test_main_raises_when_token_missing(monkeypatch):
    # Ensure TELEGRAM_TOKEN is not set
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        bot.main()


def test_main_runs_with_token(monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO)
    # Provide a dummy token
    monkeypatch.setenv("TELEGRAM_TOKEN", "dummy-token")

    # Fake application and builder to avoid network calls/daemon
    class DummyApp:
        def __init__(self):
            self.handlers = []

        def add_handler(self, handler):
            self.handlers.append(handler)

        def run_polling(self):
            logging.getLogger('bot').info('Dummy run_polling called')

    class FakeBuilder:
        def __init__(self):
            pass

        def token(self, token):
            return self

        def build(self):
            return DummyApp()

    monkeypatch.setattr(bot, "ApplicationBuilder", FakeBuilder)
    bot.main()
    assert "Starting polling" in caplog.text
    assert "Dummy run_polling called" in caplog.text


@pytest.mark.asyncio
async def test_notifyme_sends_message(tmp_path, monkeypatch):
    # Use a temporary subscribers file
    monkeypatch.setenv("SUBSCRIBERS_FILE", str(tmp_path / "subs.json"))
    class DummyMessage:
        def __init__(self):
            self.chat = Chat(id=1, type='private')
            self.from_user = User(id=1, is_bot=False, first_name='Test', last_name='Tester')
            self.replies = []
        async def reply_text(self, text):
            self.replies.append(text)
            return text

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()

    class DummyBot:
        def __init__(self, message):
            self.message = message
            self.sent = []
        async def send_message(self, chat_id, text):
            # simulate successful send by appending to message.replies
            self.message.replies.append(text)
            self.sent.append((chat_id, text))

    class DummyContext:
        def __init__(self, bot):
            self.bot = bot
            self.application = None

    update = DummyUpdate()
    bot_obj = DummyBot(update.message)
    context = DummyContext(bot_obj)
    await bot.notifyme(update, context)
    assert update.message.replies[0] == "Ini pesan yang dikirimkan oleh bot ke kamu."


@pytest.mark.asyncio
async def test_senddata_posts_payload(monkeypatch):
    import httpx
    # allow all users to send data for test
    monkeypatch.setenv("SENDDATA_ADMIN_ONLY", "0")
    monkeypatch.setenv("DATA_ENDPOINT", "https://example.com/data")

    called = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None, **kwargs):
            called['url'] = url
            called['json'] = json
            class R:
                status_code = 201
            return R()

    monkeypatch.setattr(httpx, 'AsyncClient', FakeClient)

    class DummyMessage:
        def __init__(self):
            self.chat = Chat(id=2, type='private')
            self.from_user = User(id=2, is_bot=False, first_name='Test2', last_name='Tester2')
            self.text = '/senddata {"foo":"bar"}'
            self.replies = []
        async def reply_text(self, text):
            self.replies.append(text)
            return text

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()

    class DummyContext:
        def __init__(self):
            self.args = None
            self.bot = None

    update = DummyUpdate()
    context = DummyContext()

    # call handler
    await bot.senddata(update, context)
    # assert httpx called
    assert called['url'] == 'https://example.com/data'
    assert called['json']['from']['user_id'] == 2
    assert called['json']['payload']['foo'] == 'bar'
    assert called['json']['from']['last_name'] == 'Tester2'
    # assert user received a success message
    assert any('Data sent successfully' in r for r in update.message.replies)


@pytest.mark.asyncio
async def test_on_message_updates_subscriber(tmp_path, monkeypatch):
    # Using a temp subscribers file
    monkeypatch.setenv('SUBSCRIBERS_FILE', str(tmp_path / 'subs_on_msg.json'))

    class DummyMessage:
        def __init__(self):
            self.chat = Chat(id=7, type='private')
            self.from_user = User(id=7, is_bot=False, first_name='Joe', last_name='Blow')
            self.text = 'hi'

        async def reply_text(self, text):
            return text

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()

    update = DummyUpdate()
    context = None
    await bot.on_message(update, context)

    import json
    with open(str(tmp_path / 'subs_on_msg.json'), 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert '7' in data
    assert data['7']['first_name'] == 'Joe'
    assert data['7']['last_name'] == 'Blow'
