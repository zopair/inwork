"""SQLite domain layer for InWork's service marketplace.

This module deliberately contains no HTTP routes or authentication shortcuts.
Callers must pass an authenticated user id from a future, verified auth layer.
Private contact details are never returned by these helpers.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "inwork.sqlite3"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('requester', 'worker', 'admin')),
    display_name TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS worker_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    bio TEXT NOT NULL DEFAULT '',
    specialties_json TEXT NOT NULL DEFAULT '[]',
    latitude REAL,
    longitude REAL,
    is_available INTEGER NOT NULL DEFAULT 1 CHECK (is_available IN (0, 1)),
    whatsapp_private TEXT,
    updated_at TEXT NOT NULL,
    CHECK ((latitude IS NULL AND longitude IS NULL) OR
           (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'expired', 'rejected')),
    starts_at TEXT,
    ends_at TEXT,
    verified_by TEXT REFERENCES users(id),
    verified_at TEXT,
    payment_reference TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requester_id TEXT NOT NULL REFERENCES users(id),
    worker_id TEXT REFERENCES users(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    description TEXT NOT NULL,
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    status TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'accepted', 'in_progress', 'completed', 'cancelled')),
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    completed_at TEXT,
    CHECK (worker_id IS NULL OR worker_id <> requester_id)
);

CREATE INDEX IF NOT EXISTS idx_requests_open_category
    ON service_requests(status, category_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_requester
    ON service_requests(requester_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_worker
    ON service_requests(worker_id, status);

CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL UNIQUE REFERENCES service_requests(id) ON DELETE CASCADE,
    requester_id TEXT NOT NULL REFERENCES users(id),
    worker_id TEXT NOT NULL REFERENCES users(id),
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS identity_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'not_submitted'
        CHECK (status IN ('not_submitted', 'pending', 'verified', 'rejected')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT NOT NULL REFERENCES users(id),
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class MarketplaceError(ValueError):
    """A domain rule rejected the requested operation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a foreign-key-enforcing SQLite connection."""
    path = db_path or os.environ.get("INWORK_DB_PATH") or str(DEFAULT_DB)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def initialize_database(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def create_request(
    db_path: str,
    requester_id: str,
    category_id: int,
    description: str,
    latitude: float,
    longitude: float,
) -> int:
    """Create an open request for an active requester; returns its numeric id."""
    description = description.strip()
    if not description:
        raise MarketplaceError("وصف الخدمة مطلوب")
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise MarketplaceError("موقع الخدمة غير صالح")

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        requester = conn.execute(
            "SELECT role, is_active FROM users WHERE id = ?", (requester_id,)
        ).fetchone()
        category = conn.execute(
            "SELECT is_active FROM categories WHERE id = ?", (category_id,)
        ).fetchone()
        if not requester or requester["role"] != "requester" or not requester["is_active"]:
            raise MarketplaceError("حساب طالب الخدمة غير صالح")
        if not category or not category["is_active"]:
            raise MarketplaceError("التخصص غير متاح")

        cursor = conn.execute(
            """INSERT INTO service_requests
               (requester_id, category_id, description, latitude, longitude, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (requester_id, category_id, description, latitude, longitude, utc_now()),
        )
        return int(cursor.lastrowid)


def accept_request(db_path: str, worker_id: str, request_id: int) -> bool:
    """Atomically claim an open request. Exactly one concurrent worker can win."""
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        worker = conn.execute(
            """SELECT u.role, u.is_active, p.category_id, p.is_available
               FROM users u JOIN worker_profiles p ON p.user_id = u.id
               WHERE u.id = ?""",
            (worker_id,),
        ).fetchone()
        if not worker or worker["role"] != "worker" or not worker["is_active"]:
            raise MarketplaceError("حساب مقدم الخدمة غير صالح")
        if not worker["is_available"]:
            raise MarketplaceError("مقدم الخدمة غير متاح")

        now = utc_now()
        subscription = conn.execute(
            """SELECT 1 FROM subscriptions
               WHERE worker_id = ? AND status = 'active'
                 AND starts_at <= ? AND ends_at >= ?
               ORDER BY ends_at DESC LIMIT 1""",
            (worker_id, now, now),
        ).fetchone()
        if not subscription:
            raise MarketplaceError("اشتراك مقدم الخدمة غير نشط")

        result = conn.execute(
            """UPDATE service_requests
               SET worker_id = ?, status = 'accepted', accepted_at = ?
               WHERE id = ? AND status = 'open' AND worker_id IS NULL
                 AND category_id = ?
                 AND requester_id <> ?""",
            (worker_id, now, request_id, worker["category_id"], worker_id),
        )
        return result.rowcount == 1


def transition_request(
    db_path: str, request_id: int, worker_id: str, new_status: str
) -> bool:
    """Allow only the accepted worker to advance an accepted request."""
    allowed = {
        "in_progress": "accepted",
        "completed": "in_progress",
    }
    expected = allowed.get(new_status)
    if not expected:
        raise MarketplaceError("انتقال الحالة غير مسموح")

    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        timestamp_column = ", completed_at = ?" if new_status == "completed" else ""
        params = [new_status]
        if new_status == "completed":
            params.append(utc_now())
        params.extend([request_id, worker_id, expected])
        result = conn.execute(
            f"""UPDATE service_requests SET status = ?{timestamp_column}
                WHERE id = ? AND worker_id = ? AND status = ?""",
            params,
        )
        return result.rowcount == 1
