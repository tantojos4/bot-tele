import importlib
import os
from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_db_save_and_get_map(monkeypatch):
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    # use an in-memory sqlite async driver (aiosqlite) for fast tests
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    import db as db_module
    importlib.reload(db_module)
    assert db_module.is_db_enabled()
    # initialize tables
    await db_module.init_db()
    now = datetime.now(timezone.utc).isoformat()
    subs_map = {111: {"first_name": "A", "last_name": "B", "username": "ab", "subscribed_at": now}}
    await db_module.save_subscribers_map(subs_map)
    loaded = await db_module.get_subscribers_map()
    assert 111 in loaded
    assert loaded[111]["first_name"] == "A"


@pytest.mark.asyncio
async def test_db_nip_truncation_on_upsert(monkeypatch):
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    import db as db_module
    importlib.reload(db_module)
    assert db_module.is_db_enabled()
    await db_module.init_db()
    long_nip = 'X' * 30
    await db_module.upsert_subscriber(9999, first_name='FN', last_name='LN', username='usr', nip=long_nip)
    loaded = await db_module.get_subscriber(9999)
    assert loaded is not None
    assert len(loaded['nip']) == 18


@pytest.mark.asyncio
async def test_db_save_subscribers_map_truncates_nip(monkeypatch):
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("aiosqlite")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    import db as db_module
    importlib.reload(db_module)
    assert db_module.is_db_enabled()
    await db_module.init_db()
    now = datetime.now(timezone.utc).isoformat()
    long_nip = 'N' * 25
    subs_map = {2222: {"first_name": "A", "last_name": "B", "username": "ab", "nip": long_nip, "subscribed_at": now}}
    await db_module.save_subscribers_map(subs_map)
    loaded = await db_module.get_subscriber(2222)
    assert loaded is not None
    assert len(loaded['nip']) == 18
