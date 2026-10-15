import sqlite3

from flask import Flask, current_app, g

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    disabled INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shares (
    story_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    story_id INTEGER NOT NULL,
    slug TEXT NOT NULL,
    visibility TEXT NOT NULL,
    html TEXT
);

CREATE TABLE IF NOT EXISTS locks (
    story_id INTEGER PRIMARY KEY,
    holder_id INTEGER NOT NULL,
    expires_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS prefs (
    user_id INTEGER PRIMARY KEY,
    theme TEXT
);
"""


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    db = get_db()
    db.executescript(SCHEMA)
    db.commit()


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
