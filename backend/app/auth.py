"""Small local account/session store for the single-machine coursework app."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DB_PATH = Path(__file__).resolve().parent.parent / "storage" / "privacyguard.db"
bearer = HTTPBearer(auto_error=False)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


@contextmanager
def _connection():
    connection = _connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def _init_db() -> None:
    with _connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_user_id ON sessions(user_id);
            """
        )


_init_db()


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)


def _new_session(db: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(36)
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (int(time.time()),))
    db.execute(
        "INSERT INTO sessions(token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hashlib.sha256(token.encode()).hexdigest(), user_id, int(time.time()) + 60 * 60 * 24 * 14),
    )
    return token


def register(name: str, email: str, password: str) -> dict:
    name = name.strip()[:80]
    email = email.strip().lower()[:254]
    if not name or "@" not in email or len(password) < 8:
        raise HTTPException(400, "Enter your name, a valid email, and a password of at least 8 characters.")
    salt = secrets.token_bytes(16)
    user_id = secrets.token_hex(16)
    try:
        with _connection() as db:
            db.execute(
                "INSERT INTO users(id, name, email, salt, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, name, email, salt, _password_hash(password, salt), int(time.time())),
            )
            token = _new_session(db, user_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    return {"token": token, "user": {"id": user_id, "name": name, "email": email}}


def login(email: str, password: str) -> dict:
    email = email.strip().lower()
    with _connection() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None or not secrets.compare_digest(_password_hash(password, row["salt"]), row["password_hash"]):
            raise HTTPException(401, "Email or password is incorrect.")
        token = _new_session(db, row["id"])
    return {"token": token, "user": {"id": row["id"], "name": row["name"], "email": row["email"]}}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Sign in to continue.")
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    with _connection() as db:
        row = db.execute(
            "SELECT users.id, users.name, users.email FROM sessions JOIN users ON users.id=sessions.user_id "
            "WHERE sessions.token_hash=? AND sessions.expires_at>?",
            (token_hash, int(time.time())),
        ).fetchone()
    if row is None:
        raise HTTPException(401, "Your session expired. Sign in again.")
    return dict(row)


def revoke(credentials: HTTPAuthorizationCredentials | None) -> None:
    if credentials is None:
        return
    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()
    with _connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
