#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env.dev ]; then
  echo ".env.dev not found; please create or edit .env.dev with proper settings"
  exit 1
fi

cp .env.dev .env

./scripts/start_postgres_dev.sh

python bot.py
