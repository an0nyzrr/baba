# spidtok-server/config.py
# author: Найзер (spidos team)
"""All the knobs in one place, read from the environment so nothing secret
sits in the repo. Copy .env.example to .env and fill it in before running."""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _ids(raw: str) -> set[int]:
    return {int(x) for x in raw.replace(" ", "").split(",") if x}


# Telegram
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS = _ids(os.environ.get("ADMIN_IDS", ""))

# HTTP server the mod itself polls
HTTP_HOST = os.environ.get("HTTP_HOST", "0.0.0.0")
HTTP_PORT = int(os.environ.get("HTTP_PORT", "8080"))

# storage
DB_PATH = os.environ.get("DB_PATH", "spidtok.db")

# how often one admin action may repeat, seconds -- a brake on a stuck finger,
# not real auth (that's ADMIN_IDS)
GRANT_COOLDOWN = int(os.environ.get("GRANT_COOLDOWN", "2"))

# brand
APP_NAME = "SpidTok"
TEAM_NAME = "spidos team"
CODER_NAME = "Найзер"
CHANNEL = "https://t.me/spidoscalc"
PURCHASE_CONTACT = "https://t.me/xedazu"

# badge ids that mean something special to the server logic
BADGE_CHECKMARK = "checkmark"
