"""Utility: migrate existing JSON subscribers file to the configured Postgres DB.

Usage:
  python scripts/migrate_subscribers.py

This script is safe to run multiple times and will upsert records.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
import db


def _get_subscribers_file() -> str:
    return os.getenv("SUBSCRIBERS_FILE", "subscribers.json")


async def migrate() -> None:
    if not db.is_db_enabled():
        print("DATABASE_URL not configured or SQLAlchemy not installed. Aborting.")
        return
    # Ensure tables exist before performing save/upsert operations; helpful for fresh databases
    try:
        print("Initializing DB tables...")
        await db.init_db()
    except Exception as exc:
        print("Failed to initialize or create DB tables:", exc)
        print("Please ensure the database is reachable and you have privileges to create tables.")
        return
    file_path = _get_subscribers_file()
    if not os.path.exists(file_path):
        print(f"No subscribers file found at {file_path}. Nothing to migrate.")
        return
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:
        print("Failed to read subscribers file:", exc)
        return

    # Normalize to dict mapping
    if isinstance(data, list):
        now = datetime.now(timezone.utc).isoformat()
        subs_map = {int(cid): {"first_name": None, "last_name": None, "username": None, "nip": None, "subscribed_at": now} for cid in data}
    elif isinstance(data, dict):
        # Materialize the normalized shape if needed
        def _norm(meta):
            meta = meta or {}
            return {
                "first_name": meta.get("first_name"),
                "nip": meta.get("nip"),
                "last_name": meta.get("last_name"),
                "username": meta.get("username"),
                "subscribed_at": meta.get("subscribed_at"),
                "updated_at": meta.get("updated_at", None),
            }
        subs_map = {int(k): _norm(v) for k, v in (data or {}).items()}
    else:
        print("Unsupported subscribers.json format; aborting.")
        return

    print(f"Migrating {len(subs_map)} subscriber(s) to database...")
    await db.save_subscribers_map(subs_map)
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
