# bot-tele

A small Telegram bot updated for python-telegram-bot v20+.

Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:

   pip install -r requirements.txt

3. Copy `.env` and set your `TELEGRAM_TOKEN`.
4. Run the bot:

   python bot.py

Notes

- The token should be stored in the environment variable `TELEGRAM_TOKEN` or in the `.env` file (for local development).
- Do not commit real tokens to source control.

Security

- If you accidentally committed your bot token to the repository, rotate your token immediately via BotFather and remove it from your repository's history (tools: git filter-repo or BFG Repository Cleaner).
- Use `.env.example` to document required env variables. Never commit `.env`.

Development

- For development dependencies (linters and test tools) install `requirements-dev.txt`:

  pip install -r requirements-dev.txt

CI

- Consider adding a GitHub Actions workflow to run `pytest` and static checks on push.

Testing

- To run the test suite (from project root):

```powershell
$env:PYTHONPATH = (Get-Location).Path
pytest -q
```

Logging

The bot uses Python's `logging` module. By default the console logger prints INFO-level messages.
To change verbosity, set the `LOG_LEVEL` environment variable (DEBUG, INFO, WARNING, ERROR, CRITICAL).

Examples (PowerShell):

```powershell
# Verbose debug output
$env:LOG_LEVEL = 'DEBUG'
python .\bot.py

# Less verbose
$env:LOG_LEVEL = 'INFO'
python .\bot.py
```

Logging best practices:

- Avoid logging secrets (the token is never logged by default).
- For production, route logs to an external logger/monitoring solution (Sentry, DataDog, ELK stack).

Subscriber & dispatching

- When a user issues `/start` in a private chat, the bot will store their chat id in a subscribers file (`subscribers.json` by default). This allows the bot to proactively reach out to users later (for notifications, broadcasts, etc.).
- You can change the default subscribers file by setting `SUBSCRIBERS_FILE` environment variable.
- Optionally configure `FOLLOWUP_DELAY` (seconds) to have a follow-up message sent after start (defaults to 0 for no follow-up).
- The bot includes `/notifyme` which will make the bot send a proactive message to the user who invoked it.
- The bot includes `/broadcast <message>` to send a message to all subscribers — this command requires `ADMIN_CHAT_ID` environment variable to be set and the admin to invoke this command.

Examples (PowerShell):

```powershell
# Set up a custom subscribers file and a 10-second followup message
$env:SUBSCRIBERS_FILE = 'my_subs.json'
$env:FOLLOWUP_DELAY = '10'
$env:ADMIN_CHAT_ID = '12345678'
$env:TELEGRAM_TOKEN = '123456:ABC-DEF...'
python .\bot.py
```

Proactive send examples:

- `/notifyme` — send a proactive message to yourself
- `/broadcast Hello everyone` — admin-only: broadcast to all saved subscribers
  This runs the current unit tests which check the command handlers and main safety checks. Add more tests for additional behavior.
