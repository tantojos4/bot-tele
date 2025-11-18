#!/usr/bin/env bash
set -euo pipefail
COMPOSE_FILE="docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
  echo "Starting Postgres via docker compose: $COMPOSE_FILE"
  if command -v docker >/dev/null 2>&1; then
    docker compose -f "$COMPOSE_FILE" up -d
  else
    docker-compose -f "$COMPOSE_FILE" up -d
  fi
else
  echo "No docker-compose.yml found in project root. Exiting"
  exit 1
fi

# wait for Postgres to accept connection
HOST=127.0.0.1
PORT=5432
MAX=30
for i in $(seq 1 $MAX); do
  if nc -z $HOST $PORT >/dev/null 2>&1; then
    echo "Postgres reachable"
    break
  fi
  sleep 1
done

if ! nc -z $HOST $PORT >/dev/null 2>&1; then
  echo "Postgres not reachable after waiting; exiting"
  exit 1
fi

# initialize DB schema
export DATABASE_URL="postgresql+asyncpg://botuser:botpass@127.0.0.1:5432/bottele"
python -c "import asyncio, db; asyncio.run(db.init_db()); print('DB init finished')"

echo "Dev Postgres is ready. Run bot.py with the environment variables from .env.dev"
