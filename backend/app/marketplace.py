"""SQLite domain layer for InWork's service marketplace.

This module deliberately contains no HTTP routes or authentication shortcuts.
Callers must pass an authenticated user id from a future, verified auth layer.
Private contact details are never returned by these helpers.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
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
    phone_private TEXT,
    updated_at TEXT NOT NULL,
    CHECK ((latitude IS NULL AND longitude IS NULL) OR
           (latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'active', 'expired', 'rejected')),
    amount_egp INTEGER NOT NULL DEFAULT 100 CHECK (amount_egp > 0),
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
    contact_shared INTEGER NOT NULL DEFAULT 0 CHECK (contact_shared IN (0, 1)),
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


@contextmanager
def connect(db_path: Optional[str] = None):
    """Yield a foreign-key-enforcing connection and always close it."""
    path = db_path or os.environ.get("INWORK_DB_PATH") or str(DEFAULT_DB)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
        if conn.in_transaction:
            conn.commit()
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        # Safe additive migrations for databases created by earlier branch commits.
        profile_columns = {row["name"] for row in conn.execute("PRAGMA table_info(worker_profiles)")}
        if "phone_private" not in profile_columns:
            conn.execute("ALTER TABLE worker_profiles ADD COLUMN phone_private TEXT")
        request_columns = {row["name"] for row in conn.execute("PRAGMA table_info(service_requests)")}
        if "contact_shared" not in request_columns:
            conn.execute("ALTER TABLE service_requests ADD COLUMN contact_shared INTEGER NOT NULL DEFAULT 0")


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


def list_categories(db_path: str) -> list[dict]:
    with connect(db_path) as conn:
        return [dict(row) for row in conn.execute(
            "SELECT id, name_ar FROM categories WHERE is_active=1 ORDER BY name_ar"
        ).fetchall()]


def search_workers(db_path: str, category_id: int, latitude: float,
                   longitude: float, radius_km: float = 15) -> list[dict]:
    import math
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise MarketplaceError("موقع البحث غير صالح")
    if not (1 <= radius_km <= 100):
        raise MarketplaceError("نطاق البحث يجب أن يكون بين 1 و100 كم")
    lat_delta = radius_km / 110.574
    lon_scale = max(0.01, 111.320 * math.cos(math.radians(latitude)))
    lon_delta = radius_km / lon_scale
    with connect(db_path) as conn:
        rows = conn.execute(
            """SELECT u.id, u.display_name, p.bio, p.specialties_json, p.latitude, p.longitude,
                      c.name_ar AS category
               FROM worker_profiles p JOIN users u ON u.id=p.user_id
               JOIN categories c ON c.id=p.category_id
               WHERE u.role='worker' AND u.is_active=1 AND p.is_available=1
                 AND p.category_id=? AND p.latitude BETWEEN ? AND ?
                 AND p.longitude BETWEEN ? AND ?
                 AND EXISTS (SELECT 1 FROM subscriptions s WHERE s.worker_id=u.id
                    AND s.status='active' AND s.starts_at<=? AND s.ends_at>=?)""",
            (category_id, latitude-lat_delta, latitude+lat_delta,
             longitude-lon_delta, longitude+lon_delta, utc_now(), utc_now())
        ).fetchall()
    found = []
    for row in rows:
        lat1, lat2 = math.radians(latitude), math.radians(row["latitude"])
        dlat = lat2-lat1
        dlon = math.radians(row["longitude"]-longitude)
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        distance = 6371 * 2 * math.asin(math.sqrt(a))
        if distance <= radius_km:
            found.append({
                "id": row["id"], "display_name": row["display_name"],
                "bio": row["bio"], "specialties": row["specialties_json"],
                "category": row["category"], "distance_km": round(distance, 1),
                # Approximate map point only; never expose exact stored coordinates publicly.
                "latitude": round(row["latitude"], 2),
                "longitude": round(row["longitude"], 2),
            })
    return sorted(found, key=lambda item: item["distance_km"])


def list_worker_requests(db_path: str, worker_id: str, radius_km: float = 25) -> list[dict]:
    import math
    with connect(db_path) as conn:
        worker = conn.execute(
            "SELECT category_id, latitude, longitude FROM worker_profiles WHERE user_id=?",
            (worker_id,)
        ).fetchone()
        if not worker:
            raise MarketplaceError("ملف مقدم الخدمة غير موجود")
        active_subscription = conn.execute(
            """SELECT 1 FROM subscriptions WHERE worker_id=? AND status='active'
               AND starts_at<=? AND ends_at>=? LIMIT 1""",
            (worker_id, utc_now(), utc_now())
        ).fetchone()
        if not active_subscription:
            raise MarketplaceError("يلزم تفعيل الاشتراك لعرض الطلبات")
        rows = conn.execute(
            """SELECT r.id, r.description, r.latitude, r.longitude, r.created_at,
                      c.name_ar AS category, u.display_name AS requester_name
               FROM service_requests r JOIN categories c ON c.id=r.category_id
               JOIN users u ON u.id=r.requester_id
               WHERE r.status='open' AND r.category_id=?
               ORDER BY r.created_at DESC LIMIT 100""",
            (worker["category_id"],)
        ).fetchall()
    results = []
    for row in rows:
        distance = None
        if worker["latitude"] is not None and worker["longitude"] is not None:
            p1, p2 = math.radians(worker["latitude"]), math.radians(row["latitude"])
            dp = p2-p1
            dl = math.radians(row["longitude"]-worker["longitude"])
            a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
            distance = 6371 * 2 * math.asin(math.sqrt(a))
            if distance > radius_km:
                continue
        results.append({
            "id": row["id"], "description": row["description"],
            "category": row["category"], "requester_name": row["requester_name"],
            "distance_km": round(distance, 1) if distance is not None else None,
            "latitude": round(row["latitude"], 2), "longitude": round(row["longitude"], 2),
            "created_at": row["created_at"],
        })
    return results


def list_user_requests(db_path: str, user_id: str, role: str) -> list[dict]:
    if role == "requester":
        predicate, params = "r.requester_id=?", (user_id,)
    elif role == "worker":
        predicate, params = "r.worker_id=?", (user_id,)
    else:
        raise MarketplaceError("الصلاحية غير كافية")
    with connect(db_path) as conn:
        rows = conn.execute(
            f"""SELECT r.id, r.description, r.status, r.created_at, r.accepted_at,
                       r.completed_at, c.name_ar AS category,
                       CASE WHEN r.requester_id=? THEN wu.display_name ELSE ru.display_name END AS other_party
                FROM service_requests r JOIN categories c ON c.id=r.category_id
                JOIN users ru ON ru.id=r.requester_id
                LEFT JOIN users wu ON wu.id=r.worker_id
                WHERE {predicate} ORDER BY r.created_at DESC""",
            (user_id, *params)
        ).fetchall()
        return [dict(row) for row in rows]


def update_worker_profile(db_path: str, worker_id: str, bio: str,
                          latitude: float, longitude: float, available: bool,
                          phone: Optional[str], whatsapp: Optional[str]) -> None:
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise MarketplaceError("الموقع غير صالح")
    if len(bio) > 1000 or (phone and len(phone) > 32) or (whatsapp and len(whatsapp) > 32):
        raise MarketplaceError("بعض البيانات أطول من المسموح")
    with connect(db_path) as conn:
        result = conn.execute(
            """UPDATE worker_profiles SET bio=?, latitude=?, longitude=?, is_available=?,
                      phone_private=?, whatsapp_private=?, updated_at=?
               WHERE user_id=?""",
            (bio.strip(), latitude, longitude, 1 if available else 0,
             phone, whatsapp, utc_now(), worker_id)
        )
        if result.rowcount != 1:
            raise MarketplaceError("ملف مقدم الخدمة غير موجود")


def share_request_contact(db_path: str, requester_id: str, request_id: int) -> bool:
    with connect(db_path) as conn:
        result = conn.execute(
            """UPDATE service_requests SET contact_shared=1
               WHERE id=? AND requester_id=? AND status IN ('accepted','in_progress')""",
            (request_id, requester_id)
        )
        return result.rowcount == 1


def get_request_contact(db_path: str, user_id: str, role: str, request_id: int) -> Optional[dict]:
    with connect(db_path) as conn:
        row = conn.execute(
            """SELECT r.requester_id, r.worker_id, r.status, r.contact_shared,
                      p.phone_private, p.whatsapp_private
               FROM service_requests r JOIN worker_profiles p ON p.user_id=r.worker_id
               WHERE r.id=?""", (request_id,)
        ).fetchone()
        if not row or row["status"] not in ("accepted", "in_progress", "completed"):
            return None
        if role == "requester" and row["requester_id"] == user_id:
            allowed = bool(row["contact_shared"])
        elif role == "worker" and row["worker_id"] == user_id:
            allowed = bool(row["contact_shared"])
        else:
            allowed = False
        if not allowed:
            return None
        return {"phone": row["phone_private"], "whatsapp": row["whatsapp_private"]}


def cancel_request(db_path: str, requester_id: str, request_id: int) -> bool:
    with connect(db_path) as conn:
        result = conn.execute(
            """UPDATE service_requests SET status='cancelled'
               WHERE id=? AND requester_id=? AND status='open'""",
            (request_id, requester_id)
        )
        return result.rowcount == 1
