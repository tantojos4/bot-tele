from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict
import os
import asyncio
import logging
from typing import Optional, List
from dotenv import load_dotenv
from telegram import Bot
from bot import _load_subscribers_map, _save_subscribers_map, _normalize_nip
from datetime import datetime, timezone

load_dotenv()
app = FastAPI()
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
NOTIFY_API_KEY = os.getenv("NOTIFY_API_KEY")
NOTIFY_CONCURRENCY = int(os.getenv("NOTIFY_CONCURRENCY", "10"))

# Lazy initialize bot so server can start even if token is missing at import time
bot = None

def get_bot():
    global bot
    if bot is not None:
        return bot
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        return None
    bot = Bot(token)
    return bot


class NotifyRequest(BaseModel):
    message: str
    chat_id: Optional[int] = None
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nip: Optional[str] = None
    model_config = ConfigDict(extra='forbid')


class SubscriberUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    nip: Optional[str] = None
    model_config = ConfigDict(extra='forbid')


async def _send_to(chat_id: int, message: str, semaphore: asyncio.Semaphore):
    async with semaphore:
        try:
            b = get_bot()
            if b is None:
                logger.error("TELEGRAM_TOKEN is not configured; cannot send message")
                return False
            await b.send_message(chat_id=chat_id, text=message)
            return True
        except Exception as e:
            logger.exception("Failed to send message to %s: %s", chat_id, e)
            return False


def _check_api_key(request: Request):
    if NOTIFY_API_KEY:
        header = request.headers.get("X-API-KEY")
        if not header or header != NOTIFY_API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/notify")
async def notify(request: Request, payload: NotifyRequest):
    _check_api_key(request)
    if payload.chat_id:
        b = get_bot()
        if b is None:
            raise HTTPException(status_code=500, detail="Server not configured with TELEGRAM_TOKEN")
        ok = await b.send_message(chat_id=payload.chat_id, text=payload.message)
        return {"sent": 1, "ok": True}
    # targeting: username / first_name
    subs_map = await _load_subscribers_map()
    if payload.username:
        # exact match username (case-insensitive)
        targets = [cid for cid, meta in subs_map.items() if meta and meta.get("username") and meta.get("username").lower() == payload.username.lower()]
    elif payload.first_name:
        # substring match on first name (case-insensitive)
        targets = [cid for cid, meta in subs_map.items() if meta and meta.get("first_name") and payload.first_name.lower() in meta.get("first_name").lower()]
    elif payload.last_name:
        # substring match on last name (case-insensitive)
        targets = [cid for cid, meta in subs_map.items() if meta and meta.get("last_name") and payload.last_name.lower() in meta.get("last_name").lower()]
    else:
        # broadcast to all
        targets = list(subs_map.keys())
    if payload.nip:
        # exact match nip value (case-sensitive); normalize input first to ensure consistent matching
        target_nip = _normalize_nip(payload.nip)
        targets = [cid for cid, meta in subs_map.items() if meta and meta.get("nip") and meta.get("nip") == target_nip]

    if not targets:
        return {"sent": 0, "ok": True}
    b = get_bot()
    if b is None:
        raise HTTPException(status_code=500, detail="Server not configured with TELEGRAM_TOKEN")
    semaphore = asyncio.Semaphore(NOTIFY_CONCURRENCY)
    tasks = [
        asyncio.create_task(_send_to(cid, payload.message, semaphore)) for cid in targets
    ]
    results = await asyncio.gather(*tasks)
    sent = sum(1 for r in results if r)
    return {"sent": sent, "ok": True}


@app.get("/subscribers")
async def get_subscribers(request: Request):
    _check_api_key(request)
    subs_map = await _load_subscribers_map()
    # Convert keys to strings for JSON serialization
    return {str(k): v for k, v in subs_map.items()}


@app.put("/subscribers/{chat_id}")
async def update_subscriber(request: Request, chat_id: int, payload: SubscriberUpdate):
    _check_api_key(request)
    subs_map = await _load_subscribers_map()
    meta = subs_map.get(int(chat_id), {})
    if payload.first_name is not None:
        meta["first_name"] = payload.first_name
    if payload.last_name is not None:
        meta["last_name"] = payload.last_name
    if payload.username is not None:
        meta["username"] = payload.username
    if payload.nip is not None:
        meta["nip"] = _normalize_nip(payload.nip)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    subs_map[int(chat_id)] = meta
    await _save_subscribers_map(subs_map)
    return {str(chat_id): meta}


@app.post("/subscribers/{chat_id}/sync")
async def sync_subscriber(request: Request, chat_id: int):
    _check_api_key(request)
    b = get_bot()
    if b is None:
        raise HTTPException(status_code=500, detail="Server not configured with TELEGRAM_TOKEN")
    # try to get chat info from Telegram
    try:
        chat = await b.get_chat(chat_id)
    except Exception as e:
        logger.exception("Failed to fetch chat info for %s: %s", chat_id, e)
        raise HTTPException(status_code=404, detail=f"Chat {chat_id} not found or not accessible")
    subs_map = await _load_subscribers_map()
    meta = subs_map.get(int(chat_id), {})
    meta["first_name"] = getattr(chat, "first_name", None)
    meta["last_name"] = getattr(chat, "last_name", None)
    meta["username"] = getattr(chat, "username", None)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    subs_map[int(chat_id)] = meta
    await _save_subscribers_map(subs_map)
    return {str(chat_id): meta}


@app.post("/subscribers/sync")
async def sync_all_subscribers(request: Request):
    _check_api_key(request)
    b = get_bot()
    if b is None:
        raise HTTPException(status_code=500, detail="Server not configured with TELEGRAM_TOKEN")
    subs_map = await _load_subscribers_map()
    if not subs_map:
        return {"updated": 0, "ok": True}
    semaphore = asyncio.Semaphore(NOTIFY_CONCURRENCY)
    updated = 0
    async def _sync_one(cid):
        nonlocal updated
        try:
            chat = await b.get_chat(cid)
            meta = subs_map.get(int(cid), {})
            meta["first_name"] = getattr(chat, "first_name", None)
            meta["last_name"] = getattr(chat, "last_name", None)
            meta["username"] = getattr(chat, "username", None)
            meta["updated_at"] = datetime.now(timezone.utc).isoformat()
            subs_map[int(cid)] = meta
            updated += 1
        except Exception:
            logger.exception("Failed to sync chat %s", cid)
        finally:
            return True
    tasks = [asyncio.create_task(_sync_one(cid)) for cid in subs_map.keys()]
    await asyncio.gather(*tasks)
    await _save_subscribers_map(subs_map)
    return {"updated": updated, "ok": True}


if __name__ == "__main__":
    # simple debug server; for production use uvicorn directly
    import uvicorn

    uvicorn.run("notify_api:app", host="0.0.0.0", port=8000, log_level="info")
