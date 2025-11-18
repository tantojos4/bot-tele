import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load environment variables from a .env file if present
load_dotenv()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    await message.reply_text("Halo! Selamat datang di bot saya.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when the /help command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    await message.reply_text("Gunakan /start untuk memulai bot.")


async def haysay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a short 'hay say' message when the /haysay command is issued."""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if message is None:
        return
    await message.reply_text("hay say")


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

    # Start the bot. This call blocks until the process is stopped (ctrl-c).
    app.run_polling()


if __name__ == "__main__":
    main()