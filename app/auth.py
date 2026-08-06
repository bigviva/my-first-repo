"""Authentication and role-based authorization.

Local credential auth with server-side sessions, built so an enterprise
IdP (Entra/Azure AD via OIDC) can replace the login step later without
touching the permission model: SSO would create/match the user row and
mint the same session token.

Roles:
- admin:    everything, including user management
- quality:  full read/write on all records
- viewer:   read-only
- supplier: sees only CARs addressed to their supplier_name; may submit
            responses to them and nothing else
"""
import hashlib
import os
import secrets
import sqlite3
from typing import Optional

from fastapi import Cookie, Depends, HTTPException

from . import database as db

SESSION_COOKIE = "cat_session"
SESSION_TTL_HOURS = 12
_PBKDF2_ITERATIONS = 240_000

ROLES = ("admin", "quality", "viewer", "supplier")
WRITE_ROLES = ("admin", "quality")


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), _PBKDF2_ITERATIONS).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt), stored)


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_hex(32)
    conn.execute(
        f"""INSERT INTO sessions (token, user_id, expires_at)
            VALUES (?, ?, datetime('now', '+{SESSION_TTL_HOURS} hours'))""",
        (token, user_id))
    return token


def destroy_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def user_for_token(conn: sqlite3.Connection, token: str):
    if not token:
        return None
    row = conn.execute(
        """SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token = ? AND s.expires_at > datetime('now') AND u.active = 1""",
        (token,)).fetchone()
    return dict(row) if row else None


def bootstrap_admin() -> None:
    """Ensure at least one admin exists. Uses ADMIN_EMAIL/ADMIN_PASSWORD env
    vars, falling back to a dev default that must be changed in production."""
    email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("ADMIN_PASSWORD", "change-me-now")
    with db.get_conn() as conn:
        has_admin = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE role = 'admin'").fetchone()["n"]
        if has_admin:
            return
        conn.execute(
            """INSERT INTO users (name, email, department, role, password_hash)
               VALUES (?, ?, 'Administration', 'admin', ?)
               ON CONFLICT(email) DO UPDATE SET role = 'admin',
                   password_hash = excluded.password_hash""",
            ("Administrator", email, hash_password(password)))
    if "ADMIN_PASSWORD" not in os.environ:
        print(f"[auth] Bootstrapped admin '{email}' with the DEV DEFAULT password "
              "'change-me-now' — set ADMIN_EMAIL/ADMIN_PASSWORD in production.")


def current_user(cat_session: Optional[str] = Cookie(default=None)) -> dict:
    with db.get_conn() as conn:
        user = user_for_token(conn, cat_session or "")
    if user is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return user


def require_writer(user: dict = Depends(current_user)) -> dict:
    if user["role"] not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="requires quality or admin role")
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="requires admin role")
    return user


def forbid_supplier(user: dict = Depends(current_user)) -> dict:
    """Reads open to internal roles; suppliers are scoped to their own CARs."""
    if user["role"] == "supplier":
        raise HTTPException(status_code=403, detail="supplier accounts are limited to their own CARs")
    return user
