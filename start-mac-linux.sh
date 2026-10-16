#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
pip install -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo 'ISI OPENAI_API_KEY dan APP_ACCESS_PIN di file .env sebelum Generate.'
fi
python app.py
