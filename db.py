# spidtok-server/db.py
# author: Найзер (spidos team)
"""One sqlite file. Badges, who granted them, and the donation queue waiting
on an admin's yes or no."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS badges (
    uid        TEXT NOT NULL,
    badge_id   TEXT NOT NULL,
    colour     TEXT,
    title      TEXT,
    text       TEXT,
    button     TEXT,
    granted_by INTEGER,
    granted_at REAL,
    PRIMARY KEY (uid, badge_id)
);

CREATE TABLE IF NOT EXISTS donations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id  INTEGER NOT NULL,
    tg_username TEXT,
    tt_username TEXT,
    tt_uid      TEXT,
    note        TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    created_at  REAL,
    decided_at  REAL,
    decided_by  INTEGER
);
"""

#: badge styling the client falls back on when a row doesn't set its own.
#: edited here rather than in the apk -- nothing ships to update this.
BADGE_DEFAULTS = {
    "checkmark": {"colour": "3BA7FF", "title": "SpidTok",
                  "text": "подтверждённый донатер SpidTok",
                  "button": "Понятно"},
    "coder": {"colour": "8DD1B0", "title": "SpidTok",
              "text": "в команде spidos team", "button": "Понятно"},
    "owner": {"colour": "FF6F6F", "title": "SpidTok",
              "text": "владелец SpidTok", "button": "Понятно"},
    "supporter": {"colour": "B388FF", "title": "SpidTok",
                  "text": "поддержал SpidTok", "button": "Понятно"},
}


@contextmanager
def connect():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)


# ------------------------------------------------------------------ badges

def grant_badge(uid: str, badge_id: str, granted_by: int, **overrides) -> None:
    row = {**BADGE_DEFAULTS.get(badge_id, {}), **overrides}
    with connect() as conn:
        conn.execute(
            """INSERT INTO badges (uid, badge_id, colour, title, text, button,
                                    granted_by, granted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(uid, badge_id) DO UPDATE SET
                 colour=excluded.colour, title=excluded.title,
                 text=excluded.text, button=excluded.button,
                 granted_by=excluded.granted_by, granted_at=excluded.granted_at""",
            (uid, badge_id, row.get("colour"), row.get("title"),
             row.get("text"), row.get("button"), granted_by, time.time()),
        )


def revoke_badge(uid: str, badge_id: str) -> bool:
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM badges WHERE uid = ? AND badge_id = ?", (uid, badge_id)
        )
        return cur.rowcount > 0


def badges_for(uid: str) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM badges WHERE uid = ? ORDER BY granted_at", (uid,)
        ).fetchall()


def all_badges() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM badges ORDER BY uid, badge_id").fetchall()


# --------------------------------------------------------------- donations

def queue_donation(tg_user_id: int, tg_username: str | None,
                    tt_username: str, tt_uid: str | None, note: str = "") -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO donations (tg_user_id, tg_username, tt_username,
                                       tt_uid, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (tg_user_id, tg_username, tt_username, tt_uid, note, time.time()),
        )
        return cur.lastrowid


def pending_donations() -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM donations WHERE status = 'pending' ORDER BY created_at"
        ).fetchall()


def get_donation(donation_id: int) -> sqlite3.Row | None:
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM donations WHERE id = ?", (donation_id,)
        ).fetchone()


def decide_donation(donation_id: int, approved: bool, decided_by: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE donations SET status = ?, decided_at = ?, decided_by = ? WHERE id = ?",
            ("approved" if approved else "rejected", time.time(), decided_by, donation_id),
        )
