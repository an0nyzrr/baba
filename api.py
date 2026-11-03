# spidtok-server/api.py
# author: Найзер (spidos team)
"""What the mod itself polls. Three read-only endpoints, no auth needed
because nothing here is a secret -- it's the same badges.json/version.json
shape the client already knows how to read, just generated from the database
instead of hand-edited.

    GET /badges.json   every badge, grouped the way the client expects
    GET /version.json  latest release + where to get it
    GET /links.json     the "about" card: channel, who to buy from, credits
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
import db

# ----------------------------------------------------------------- version
# edited by hand on a release, or by a deploy script -- not by the bot.
VERSION = {
    "version": "1.0.0",
    "url": "https://example.invalid/spidtok-latest.apk",
    "notes": "первый билд SpidTok",
}


def badges_payload() -> dict:
    grouped: dict[str, dict] = {}
    for row in db.all_badges():
        bucket = grouped.setdefault(row["badge_id"], {
            "id": row["badge_id"],
            "colour": row["colour"],
            "title": row["title"],
            "text": row["text"],
            "button": row["button"],
            "users": [],
        })
        bucket["users"].append(row["uid"])
    return {"badges": list(grouped.values())}


def links_payload() -> dict:
    return {
        "coder": config.CODER_NAME,
        "team": config.TEAM_NAME,
        "channel": config.CHANNEL,
        "purchase": config.PURCHASE_CONTACT,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "spidtok/1.0"

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/badges.json":
            self._json(badges_payload())
        elif path == "/version.json":
            self._json(VERSION)
        elif path == "/links.json":
            self._json(links_payload())
        elif path == "/healthz":
            self._json({"ok": True})
        else:
            self._json({"error": "not found"}, 404)

    def log_message(self, fmt, *args) -> None:  # quieter default logging
        print("[http]", self.address_string(), fmt % args)


def serve_forever() -> None:
    db.init()
    httpd = ThreadingHTTPServer((config.HTTP_HOST, config.HTTP_PORT), Handler)
    print(f"[http] listening on {config.HTTP_HOST}:{config.HTTP_PORT}")
    httpd.serve_forever()


def start_in_thread() -> threading.Thread:
    t = threading.Thread(target=serve_forever, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    serve_forever()
