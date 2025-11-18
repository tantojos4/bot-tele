import os
import logging
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
import ipaddress
import socket
import httpx
import asyncio
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Load environment variables from a .env file if present
load_dotenv()

# Configure logging
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


DEFAULT_SUBSCRIBERS_FILE = "subscribers.json"
FOLLOWUP_DELAY = int(os.getenv("FOLLOWUP_DELAY", "0"))
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
DATA_ENDPOINT = os.getenv("DATA_ENDPOINT")
SENDDATA_ADMIN_ONLY = os.getenv("SENDDATA_ADMIN_ONLY", "1")
ALLOWED_OUTBOUND_HOSTS = os.getenv("ALLOWED_OUTBOUND_HOSTS")


def _get_subscribers_file() -> str:
    return os.getenv("SUBSCRIBERS_FILE", DEFAULT_SUBSCRIBERS_FILE)


def _load_subscribers_map() -> dict:
    """Return mapping chat_id -> metadata dict.

    Example: {123: {"first_name": "Alice", "username": "alice", "subscribed_at": "..."}}
    """
    try:
        file_path = _get_subscribers_file()
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            # Protect against empty files
            try:
                if os.stat(file_path).st_size == 0:
                    logger.warning("Subscribers file is empty: %s", file_path)
                    return {}
            except Exception:
                # not critical
                pass
            try:
                data = json.load(f)
            except json.JSONDecodeError as exc:
                # Backup corrupted file and return empty map
                logger.exception("Invalid JSON in subscribers file %s: %s", file_path, exc)
                try:
                    backup_path = file_path + ".corrupt-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    os.rename(file_path, backup_path)
                    logger.info("Backed up corrupted subscribers file to %s", backup_path)
                except Exception:
                    logger.exception("Failed to backup corrupted subscribers file %s", file_path)
                # Write an empty map to replace the corrupted file
                try:
                    _save_subscribers_map({})
                except Exception:
                    logger.exception("Failed to initialize subscribers file after corruption %s", file_path)
                return {}
            # legacy list format: [id1, id2, ...]
            if isinstance(data, list):
                now = datetime.now(timezone.utc).isoformat()
                subs_map = {int(cid): {"first_name": None, "last_name": None, "username": None, "subscribed_at": now} for cid in data}
                # save converted format back to file
                try:
                    _save_subscribers_map(subs_map)
                except Exception:
                    logger.exception("Failed to persist converted subscribers map to %s", file_path)
                return subs_map
            # keys are strings in dict; cast to int
            if isinstance(data, dict):
                # Ensure last_name is available and normalize metadata
                def _norm(meta):
                    meta = meta or {}
                    return {
                        "first_name": meta.get("first_name"),
                        "last_name": meta.get("last_name"),
                        "username": meta.get("username"),
                        "subscribed_at": meta.get("subscribed_at"),
                        "updated_at": meta.get("updated_at", None),
                    }
                subs_map = {int(k): _norm(v) for k, v in (data or {}).items()}
                # If any entry originally omitted 'last_name', persist normalized map back to file
                try:
                    needs_write = any('last_name' not in (v or {}) for v in (data or {}).values())
                except Exception:
                    needs_write = False
                if needs_write:
                    try:
                        _save_subscribers_map(subs_map)
                        logger.info("Migrated subscribers file to include last_name: %s", file_path)
                    except Exception:
                        logger.exception("Failed to save normalized subscribers map to %s", file_path)
                return subs_map
            # unknown format
            logger.warning("Unknown subscribers file format (%s). Returning empty map.", type(data))
            return {}
    except Exception:
        logger.exception("Failed to load subscribers from %s", file_path)
        return {}


def _load_subscribers() -> set:
    try:
        return set(_load_subscribers_map().keys())
    except Exception:
        logger.exception("Failed to load subscribers")
        return set()


def _save_subscribers_map(subs_map: dict) -> None:
    try:
        file_path = _get_subscribers_file()
        # dump map with string keys for JSON
        with open(file_path, "w", encoding="utf-8") as f:
            normalized = {}
            for k, v in subs_map.items():
                v = v or {}
                normalized[str(k)] = {
                    "first_name": v.get("first_name"),
                    "last_name": v.get("last_name"),
                    "username": v.get("username"),
                    "subscribed_at": v.get("subscribed_at"),
                    "updated_at": v.get("updated_at", None),
                }
            json.dump(normalized, f)
        logger.info("Saved subscribers file %s with %d subscribers", file_path, len(normalized))
    except Exception:
        logger.exception("Failed to save subscribers to %s", file_path)


def _save_subscribers(subs: set) -> None:
    # backward-compat helper; convert set to map with minimal metadata (no names)
    subs_map = {int(cid): {"first_name": None, "last_name": None, "username": None, "subscribed_at": datetime.now(timezone.utc).isoformat()} for cid in subs}
    _save_subscribers_map(subs_map)


def add_subscriber(chat_id: int, first_name: str = None, username: str = None, last_name: str = None) -> None:
    subs_map = _load_subscribers_map()
    now = datetime.now(timezone.utc).isoformat()
    if chat_id in subs_map:
        # update metadata if changed and refresh subscribe timestamp
        meta = subs_map[int(chat_id)]
        updated = False
        if first_name and meta.get("first_name") != first_name:
            meta["first_name"] = first_name
            updated = True
        if last_name and meta.get("last_name") != last_name:
            meta["last_name"] = last_name
            updated = True
        if username and meta.get("username") != username:
            meta["username"] = username
            updated = True
        if updated:
            meta["updated_at"] = now
            subs_map[int(chat_id)] = meta
            _save_subscribers_map(subs_map)
            logger.info("Updated subscriber %s metadata: %s", chat_id, meta)
        return
    subs_map[int(chat_id)] = {
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "subscribed_at": now,
    }
    _save_subscribers_map(subs_map)
    logger.info("Added new subscriber %s metadata: %s", chat_id, subs_map[int(chat_id)])


async def _delayed_send(app, chat_id: int, text: str, delay: int):
    try:
        await asyncio.sleep(delay)
        await app.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.exception("Failed to send delayed message to %s: %s", chat_id, e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    logger.info("Received /start from user_id=%s", uid)
    await message.reply_text("Halo! Selamat datang di bot saya.")
    # Only store private chat users
    chat_type = getattr(message.chat, "type", None)
    if chat_type == "private" and uid:
        add_subscriber(uid, getattr(user, "first_name", None), getattr(user, "username", None), getattr(user, "last_name", None))
        # optional follow-up
        if FOLLOWUP_DELAY > 0 and context and getattr(context, "application", None):
            context.application.create_task(
                _delayed_send(context.application, uid, "Hai lagi! Ini pesan follow-up.", FOLLOWUP_DELAY)
            )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the /help command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    logger.info("Received /help from user_id=%s", uid)
    await message.reply_text("Gunakan /start untuk memulai bot.")


async def haysay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a short 'hay say' message when the /haysay command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    logger.info("Received /haysay from user_id=%s", uid)
    await message.reply_text("hay say")


async def notifyme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a proactive message to the user who invoked /notifyme.

    This demonstrates that the bot can send messages directly to a user's chat id.
    """
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    logger.info("Received /notifyme from user_id=%s", uid)
    if uid is None:
        return
    # Send a proactive message via bot API
    await context.bot.send_message(chat_id=uid, text="Ini pesan yang dikirimkan oleh bot ke kamu.")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generic message handler to keep subscriber metadata up-to-date.

    This runs on any private chat message and updates first_name, last_name, and username in the subscribers file.
    """
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    chat_type = getattr(message.chat, "type", None)
    if chat_type != "private" or uid is None:
        return
    # call add_subscriber; it will update metadata only if changed and not overwrite subscribed_at
    add_subscriber(uid, getattr(user, "first_name", None), getattr(user, "username", None), getattr(user, "last_name", None))


def _is_local_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except Exception:
        return False


def _validate_outbound_url(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = parsed.hostname
        if not host:
            return False
        allowed_hosts = os.getenv("ALLOWED_OUTBOUND_HOSTS", ALLOWED_OUTBOUND_HOSTS)
        if allowed_hosts:
            allowed = [h.strip().lower() for h in allowed_hosts.split(",") if h.strip()]
            return host.lower() in allowed
        # Ensure not localhost or local ip
        if host.lower() in ("localhost", "127.0.0.1", "::1"):
            return False
        if _is_local_ip(host):
            return False
        return True
    except Exception:
        return False


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts a message to all saved subscribers (admin only)."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    if str(uid) != str(ADMIN_CHAT_ID):
        await message.reply_text("Unauthorized: only admin can broadcast messages.")
        return
    text = " ".join(context.args)
    if not text:
        await message.reply_text("Usage: /broadcast <message>")
        return
    subs_map = _load_subscribers_map()
    subs = set(subs_map.keys())
    if not subs:
        await message.reply_text("No subscribers to broadcast to.")
        return
    sent = 0
    for cid in subs:
        try:
            await context.bot.send_message(chat_id=cid, text=text)
            sent += 1
        except Exception:
            logger.exception("Failed to send broadcast to %s", cid)
    await message.reply_text(f"Broadcast sent to {sent} users.")


async def senddata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send structured data from the bot to a configured DATA_ENDPOINT.

    Usage: /senddata {"key":"value"} or /senddata some text
    """
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    user = getattr(message, "from_user", None)
    uid = getattr(user, "id", None)
    # Check permissions
    if os.getenv("SENDDATA_ADMIN_ONLY", SENDDATA_ADMIN_ONLY) == "1" and str(uid) != str(ADMIN_CHAT_ID):
        await message.reply_text("Unauthorized: only admin can send data")
        return
    # Read data from args or message text
    data_text = None
    if context and getattr(context, "args", None):
        data_text = " ".join(context.args)
    else:
        # fallback to message text minus the command
        data_text = message.text or ""
        # remove command prefix if present
        if data_text.startswith("/senddata"):
            data_text = data_text[len("/senddata"):].strip()
    if not data_text:
        await message.reply_text("Usage: /senddata <json-or-text>")
        return
    # Parse JSON if present
    payload = None
    try:
        if data_text.strip().startswith("{") or data_text.strip().startswith("["):
            payload = json.loads(data_text)
        else:
            payload = {"text": data_text}
    except Exception:
        await message.reply_text("Invalid JSON payload")
        return
    endpoint = os.getenv("DATA_ENDPOINT", DATA_ENDPOINT)
    if not endpoint:
        await message.reply_text("No DATA_ENDPOINT configured on the server")
        return
    if not _validate_outbound_url(endpoint):
        await message.reply_text("DATA_ENDPOINT is invalid or not allowed")
        return
    # Build message with metadata
    final_payload = {
        "from": {"user_id": uid, "first_name": getattr(user, "first_name", None), "last_name": getattr(user, "last_name", None)},
        "chat_id": getattr(message.chat, "id", None),
        "payload": payload,
    }
    # Send to endpoint
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(endpoint, json=final_payload)
            if resp.status_code >= 200 and resp.status_code < 300:
                await message.reply_text("Data sent successfully")
            else:
                await message.reply_text(f"Failed to send data: HTTP {resp.status_code}")
    except Exception as e:
        logger.exception("Failed to post data to endpoint: %s", e)
        await message.reply_text(f"Failed to send data: {e}")


def main() -> None:
    """Main entry point. Builds the Application and starts polling."""
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise SystemExit(
            "Error: TELEGRAM_TOKEN is not set. Add it to your environment or to a .env file."
        )

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("haysay", haysay))
    app.add_handler(CommandHandler("notifyme", notifyme))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("senddata", senddata))
    # Keep subscriber metadata current on any private chat message
    app.add_handler(MessageHandler(filters.ALL, on_message))

    logger.info("Starting polling")
    try:
        # Start the bot. This call blocks until the process is stopped (ctrl-c).
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot interrupted by user")
    except Exception as e:
        logger.exception("Unhandled exception while running the bot: %s", e)
        raise
    finally:
        logger.info("Bot stopped")


if __name__ == "__main__":
    main()