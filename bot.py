import os
import logging
import json
import asyncio
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

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


def _get_subscribers_file() -> str:
    return os.getenv("SUBSCRIBERS_FILE", DEFAULT_SUBSCRIBERS_FILE)


def _load_subscribers() -> set:
    try:
        file_path = _get_subscribers_file()
        if not os.path.exists(file_path):
            return set()
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(map(int, data))
    except Exception:
        logger.exception("Failed to load subscribers from %s", file_path)
        return set()


def _save_subscribers(subs: set) -> None:
    try:
        file_path = _get_subscribers_file()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(sorted(list(map(int, subs))), f)
    except Exception:
        logger.exception("Failed to save subscribers to %s", file_path)


def add_subscriber(chat_id: int) -> None:
    subs = _load_subscribers()
    if chat_id in subs:
        return
    subs.add(int(chat_id))
    _save_subscribers(subs)


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
        add_subscriber(uid)
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
    subs = _load_subscribers()
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