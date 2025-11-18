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

This runs the current unit tests which check the command handlers and main safety checks. Add more tests for additional behavior.
