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
