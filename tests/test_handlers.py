import asyncio
import os
import pytest

from telegram import Message, User, Chat
from telegram.ext import ContextTypes

import bot

@pytest.mark.asyncio
async def test_start_and_help_handlers():
    # Build simple dummy Update with minimal fields for message.reply_text
    class DummyMessage:
        def __init__(self):
            self.text = ''
            self.chat = Chat(id=1, type='private')
            self.from_user = User(id=1, is_bot=False, first_name='Test')
            self.replies = []

        async def reply_text(self, text):
            self.replies.append(text)
            return text

    class DummyUpdate:
        def __init__(self):
            self.message = DummyMessage()

    update = DummyUpdate()
    context = None  # not used by our handlers

    # Call start handler
    await bot.start(update, context)
    assert update.message.replies[0] == "Halo! Selamat datang di bot saya."

    # Call help handler
    update = DummyUpdate()
    await bot.help_command(update, context)
    assert update.message.replies[0] == "Gunakan /start untuk memulai bot."

    # Call haysay handler
    update = DummyUpdate()
    await bot.haysay(update, context)
    assert update.message.replies[0] == "hay say"


def test_main_raises_when_token_missing(monkeypatch):
    # Ensure TELEGRAM_TOKEN is not set
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        bot.main()
