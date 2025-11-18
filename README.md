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

## VSCode / Pylance missing imports

If VSCode shows diagnostics like `Import "sqlalchemy" could not be resolved` (Pylance), it usually means the interpreter selected by VSCode doesn't have package dependencies installed.

Steps to resolve:

1. Select the Python interpreter used by your project: open Command Palette (Ctrl+Shift+P) → 'Python: Select Interpreter' → choose the virtual environment you use (e.g., `bot-tele` conda environment).
2. Install runtime dependencies into that interpreter: `pip install -r requirements.txt` (or `pip install -r requirements-dev.txt` if developing).
3. Restart the editor or reload window (Ctrl+Shift+P → 'Developer: Reload Window') so Pylance refreshes.

If you intentionally want SQLAlchemy optional for local development, the code defensively checks for it at runtime; to silence Pylance warnings instead of installing packages, you can add the setting in `.vscode/settings.json` (project workspace) to ignore missing import diagnostics from Pylance:

```json
{
  "python.analysis.diagnosticSeverityOverrides": {
    "reportMissingImports": "none"
  }
}
```

Prefer the install + interpreter selection approach so you get helpful linting & type checks.
Subscriber & dispatching

- When a user issues `/start` in a private chat, the bot will store their chat id in a subscribers file (`subscribers.json` by default). This allows the bot to proactively reach out to users later (for notifications, broadcasts, etc.).
- You can change the default subscribers file by setting `SUBSCRIBERS_FILE` environment variable.
- Optionally configure `FOLLOWUP_DELAY` (seconds) to have a follow-up message sent after start (defaults to 0 for no follow-up).
- The bot includes `/notifyme` which will make the bot send a proactive message to the user who invoked it.
- The bot includes `/broadcast <message>` to send a message to all subscribers — this command requires `ADMIN_CHAT_ID` environment variable to be set and the admin to invoke this command.

- The bot now automatically updates a subscriber's `first_name`, `last_name`, and `username` whenever it receives any private message from that user. This keeps metadata current (if someone changes their profile name) without requiring an admin action.

Examples (PowerShell):

```powershell
# Set up a custom subscribers file and a 10-second followup message
$env:SUBSCRIBERS_FILE = 'my_subs.json'
$env:FOLLOWUP_DELAY = '10'
$env:ADMIN_CHAT_ID = '12345678'
$env:TELEGRAM_TOKEN = '123456:ABC-DEF...'
python .\bot.py
```

## PostgreSQL integration (optional)

If you want to store subscribers reliably in a production-grade database, set the `DATABASE_URL` environment variable to a PostgreSQL database using the `asyncpg` driver. Example:

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://dbuser:dbpassword@db-host.example.com:5432/bottele"
$env:TELEGRAM_TOKEN = '123456:ABC-DEF...'
python .\bot.py
```

Best practices

- Use an environment variable (not a committed file) to store your database connection string.
- Prefer `asyncpg` (as shown) as it plays well with async SQLAlchemy.
- Use a secrets manager for credentials (AWS Secrets Manager, Vault, etc.) instead of embedding credentials in the environment for long-term production deployments.
- Use database migrations (Alembic) to manage schema changes in production.
- Keep the database server updated and secure; restrict access by network/firewall and use TLS for client connections where available.
- Monitor DB connection pool size (defaults are usually safe for small bots, but scale with your load.)

How the project uses DATABASE_URL

- If `DATABASE_URL` is set and the environment has SQLAlchemy and an async driver installed, the bot will use PostgreSQL and an ORM model to persist subscribers (columns: chat_id, first_name, last_name, username, subscribed_at, updated_at).
- If `DATABASE_URL` is NOT set, the project falls back to the JSON file (legacy behavior) so the bot remains simple and developer-friendly in small deployments.

## Migration helper

If you already have a `subscribers.json` file and want to move it to Postgres, use the simple migration script provided at `scripts/migrate_subscribers.py` (this will upsert the data into the configured database):

```powershell
$env:DATABASE_URL = "postgresql+asyncpg://dbuser:dbpassword@localhost:5432/bottele"
python scripts/migrate_subscribers.py
```

For production-grade migrations and versioned changes, use Alembic. The codebase includes SQLAlchemy models that make it straightforward to start Alembic-based migrations (see Alembic docs: https://alembic.sqlalchemy.org).

## Local dev with Docker Compose

This repository includes `docker-compose.yml` and convenience scripts to quickly run Postgres locally for development.

1. Start Postgres (PowerShell):

```powershell
# optional: change .env.dev values to fit your environment
.\scripts\start_postgres_dev.ps1
```

2. Start Postgres (macOS/Linux):

```bash
./scripts/start_postgres_dev.sh
```

3. The start script initializes the DB schema automatically by calling `db.init_db()` and sets the `DATABASE_URL` to the local instance.

4. You can also run the bot in the dev environment via PowerShell or bash. Example (PowerShell):

```powershell
# load env vars from .env.dev (PowerShell)
Set-Content -Path .env -Value (Get-Content .env.dev -Raw)
$env:DATABASE_URL = "postgresql+asyncpg://botuser:botpass@127.0.0.1:5432/bottele"
python .\bot.py
```

Notes

- The Postgres data is persisted under `./data/postgres` in a volume bind so the DB persists across container restarts.
- The default dev credentials are `botuser` / `botpass` / `bottele` and defined in `.env.dev` and `docker-compose.yml`. If you change them, update `DATABASE_URL` appropriately.
- If you want a throwaway DB, remove the `./data/postgres` folder.

## Testing with Postgres

If you want to run tests against a real Postgres DB, start the dev Postgres container as shown above and then run tests with the `DATABASE_URL` set in your environment.

Example (PowerShell):

```powershell
.\scripts\start_postgres_dev.ps1
# optionally set/override DATABASE_URL explicitly
$env:DATABASE_URL = 'postgresql+asyncpg://botuser:botpass@127.0.0.1:5432/bottele'
pytest -q
```

After you're done, bring down the Postgres container:

```powershell
.\scripts\stop_postgres_dev.ps1
```

## Quick dev-run helper

To run the bot locally using the dev Postgres setup, use the provided dev-run scripts.

PowerShell (Windows):

```powershell
.\scripts\dev_run.ps1
```

macOS/Linux:

```bash
./scripts/dev_run.sh
```

These scripts copy `.env.dev` into `.env`, bring up the dev Postgres container, initialize the DB schema, and run the bot in the current shell session.

## Alembic quick-start (recommended)

1. Install alembic (dev environment):

```powershell
pip install alembic
```

2. Initialize the alembic folder in your repository (one-time):

```powershell
alembic init alembic
```

3. Edit `alembic/env.py` and set the target metadata to import your SQLAlchemy models (for example: `from db import Base` then set `target_metadata = Base.metadata`). This allows `--autogenerate` to inspect the models.

4. Generate a migration:

```powershell
alembic revision --autogenerate -m "create subscribers table"
```

5. Apply the migration to your DB:

```powershell
alembic upgrade head
```

Using Alembic ensures that production schema changes are versioned and applied cleanly across environments.

Proactive send examples:

- `/notifyme` — send a proactive message to yourself
- `/broadcast Hello everyone` — admin-only: broadcast to all saved subscribers

Notify API server (for your app)

You can expose a simple API that lets your application trigger notifications to users who previously started the bot. The included `notify_api.py` is a small FastAPI app that provides a `/notify` endpoint.

Input validation

- The notify API enforces a strict input schema via Pydantic. `POST /notify` expects a JSON object with a string `message` and optional targeting fields (`chat_id`, `username`, `first_name`). `PUT /subscribers/{chat_id}` accepts only `first_name` and `username`. Any extraneous fields (including full Telegram update payloads) will be rejected with a 422 response.
- The notify API enforces a strict input schema via Pydantic. `POST /notify` expects a JSON object with a string `message` and optional targeting fields (`chat_id`, `username`, `first_name`, `last_name`). `PUT /subscribers/{chat_id}` accepts only `first_name`, `last_name` and `username`. Any extraneous fields (including full Telegram update payloads) will be rejected with a 422 response.

Auth

- `NOTIFY_API_KEY` header must be set when calling the `/notify` endpoint. Configure it in `.env` as `NOTIFY_API_KEY`.

Examples

- Broadcast to all subscribers

```powershell
curl -X POST -H "Content-Type: application/json" -H "X-API-KEY: your_secret_key" http://localhost:8000/notify -d '{"message": "Announcement"}'
```

- Target a single chat id

```powershell
curl -X POST -H "Content-Type: application/json" -H "X-API-KEY: your_secret_key" http://localhost:8000/notify -d '{"message": "Hello user", "chat_id": 123456789}'
```

Start the server (development):

```powershell
uvicorn notify_api:app --host 0.0.0.0 --port 8000 --reload
```

The server will use `TELEGRAM_TOKEN` from the environment to create the sending bot instance. Prefer a secure network and firewall rules for the notify API to prevent unauthorized use.
Send data from bot to external service

- `/senddata <json-or-text>` — the bot will POST JSON payload to a configured `DATA_ENDPOINT` URL.
  Notes about targeting

- Use `username` to target unique users — Telegram usernames are globally unique and the most reliable way to address a specific user.
- Using `first_name` may match multiple users and will send to all who match the substring; use with care.

Environment variables:

- `DATA_ENDPOINT`: the outbound HTTPS URL to POST data to. (e.g., `https://yourserver.example/api/data`). Must be HTTPS.
- `SENDDATA_ADMIN_ONLY`: set to `1` (default) to allow only admin (set via `ADMIN_CHAT_ID`) to use `/senddata`. Set to `0` to allow all users.
- `ALLOWED_OUTBOUND_HOSTS`: optional comma-separated list of hosts allowed (ex: `example.com,api.example.com`). If set, only these hosts are allowed. If not set, hosts will be validated against localhost/private IPs and require HTTPS.

Security:

- The bot will validate outbound URLs to prevent SSRF: it enforces HTTPS and will block localhost or private IP addresses. If you want to allow a set of hosts, use `ALLOWED_OUTBOUND_HOSTS`.

Targeted notifications

- The `notify_api` supports filtering subscribers by `username` (exact match) or `first_name` (case-insensitive substring match). Use these fields in the POST body when calling `/notify`.

Examples:

```powershell
# send to a specific username
curl -X POST -H "Content-Type: application/json" -H "X-API-KEY: your_secret_key" http://localhost:8000/notify -d '{"message": "Hello Alice", "username": "alice"}'

# send to users whose first name contains 'john' (case-insensitive)
curl -X POST -H "Content-Type: application/json" -H "X-API-KEY: your_secret_key" http://localhost:8000/notify -d '{"message": "Hello John", "first_name": "john"}'
```

Listing subscribers

- For convenience, `GET /subscribers` returns the subscribers mapping stored by the bot (requires `X-API-KEY` header). This is useful for debugging and verifying saved first_name/username metadata.
- For convenience, `GET /subscribers` returns the subscribers mapping stored by the bot (requires `X-API-KEY` header). This is useful for debugging and verifying saved first_name/last_name/username metadata. You can also use `POST /subscribers/{chat_id}/sync` to fetch fresh information from Telegram's `getChat` for an individual chat, or `POST /subscribers/sync` to update all saved subscribers.

Migration from legacy subscriber list

- Older versions of this project stored subscribers as a simple JSON list (e.g., `[1, 12345]`). The current version stores a mapping with metadata (chat_id -> {first_name, username, subscribed_at}).
- Older versions of this project stored subscribers as a simple JSON list (e.g., `[1, 12345]`). The current version stores a mapping with metadata (chat_id -> {first_name, last_name, username, subscribed_at}).
- On startup, the bot will detect the legacy list format and automatically convert it to the new mapping format, saving the new file. This happens transparently; after the conversion `GET /subscribers` will return the mapping.
  This runs the current unit tests which check the command handlers and main safety checks. Add more tests for additional behavior.
