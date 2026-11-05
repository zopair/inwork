"""Password authentication and revocable opaque sessions for InWork."""
from __future__ import annotations
import hashlib, hmac, secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from .marketplace import connect, utc_now

PBKDF2_ROUNDS = 310_000
SESSION_DAYS = 7
MAX_LOGIN_FAILURES = 5
DUMMY_PASSWORD_HASH = "pbkdf2_sha256$310000$00112233445566778899aabbccddeeff$" + hashlib.pbkdf2_hmac("sha256", b"not-a-real-password", bytes.fromhex("00112233445566778899aabbccddeeff"), 310000).hex()
LOCKOUT_MINUTES = 15

class AuthenticationError(ValueError):
    pass

def _password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return "pbkdf2_sha256$" + str(PBKDF2_ROUNDS) + "$" + salt.hex() + "$" + digest.hex()

def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False

def _session_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _utc_after(minutes: int = 0, days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes, days=days)).isoformat(timespec="seconds")

def initialize_auth_schema(db_path: Optional[str] = None) -> None:
    with connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_auth (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL, created_at TEXT NOT NULL, revoked_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id, expires_at);
        CREATE TABLE IF NOT EXISTS auth_login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email_key TEXT NOT NULL,
            ip_key TEXT NOT NULL, succeeded INTEGER NOT NULL CHECK (succeeded IN (0,1)),
            attempted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_auth_attempts_lookup
            ON auth_login_attempts(email_key, ip_key, attempted_at);
        CREATE TABLE IF NOT EXISTS auth_registration_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_key TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_auth_registration_ip
            ON auth_registration_attempts(ip_key, attempted_at);
        """)

def register_user(db_path: str, email: str, password: str, display_name: str,
                  role: str, category_id: Optional[int] = None) -> dict:
    email = email.strip().lower()
    display_name = display_name.strip()
    if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise AuthenticationError("البريد الإلكتروني غير صالح")
    if len(password) < 12 or len(password) > 128:
        raise AuthenticationError("كلمة المرور يجب أن تكون من 12 إلى 128 حرفًا")
    if not display_name or len(display_name) > 80:
        raise AuthenticationError("الاسم مطلوب وبحد أقصى 80 حرفًا")
    if role not in ("requester", "worker"):
        raise AuthenticationError("نوع الحساب غير مسموح بالتسجيل الذاتي")
    if role == "worker" and category_id is None:
        raise AuthenticationError("اختيار التخصص مطلوب لمقدم الخدمة")
    user_id, now = secrets.token_urlsafe(18), utc_now()
    password_hash = _password_hash(password)
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if role == "worker":
            category = conn.execute("SELECT id FROM categories WHERE id=? AND is_active=1", (category_id,)).fetchone()
            if not category:
                raise AuthenticationError("التخصص غير متاح")
        try:
            conn.execute("INSERT INTO users (id,role,display_name,created_at) VALUES (?,?,?,?)",
                         (user_id, role, display_name, now))
            conn.execute("INSERT INTO user_auth (user_id,email,password_hash,created_at) VALUES (?,?,?,?)",
                         (user_id, email, password_hash, now))
            if role == "worker":
                conn.execute("INSERT INTO worker_profiles (user_id,category_id,updated_at) VALUES (?,?,?)",
                             (user_id, category_id, now))
        except Exception as exc:
            if "UNIQUE constraint failed: user_auth.email" in str(exc):
                raise AuthenticationError("البريد الإلكتروني مستخدم بالفعل") from exc
            raise
    return {"id": user_id, "email": email, "display_name": display_name, "role": role}

def login(db_path: str, email: str, password: str, ip_address: str) -> tuple[dict, str]:
    email_key, ip_key = email.strip().lower()[:254], (ip_address or "unknown")[:64]
    now, cutoff = utc_now(), _utc_after(minutes=-LOCKOUT_MINUTES)
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        failures = conn.execute(
            "SELECT COUNT(*) AS n FROM auth_login_attempts WHERE email_key=? AND ip_key=? AND succeeded=0 AND attempted_at>=?",
            (email_key, ip_key, cutoff)).fetchone()["n"]
        if failures >= MAX_LOGIN_FAILURES:
            raise AuthenticationError("محاولات كثيرة. حاول مرة أخرى بعد 15 دقيقة")
        row = conn.execute(
            """SELECT u.id,u.role,u.display_name,u.is_active,a.password_hash
               FROM user_auth a JOIN users u ON u.id=a.user_id WHERE a.email=? COLLATE NOCASE""",
            (email_key,)).fetchone()
        password_ok = _verify_password(password, row["password_hash"] if row else DUMMY_PASSWORD_HASH)
        valid = bool(row and row["is_active"] and password_ok)
        conn.execute("INSERT INTO auth_login_attempts (email_key,ip_key,succeeded,attempted_at) VALUES (?,?,?,?)",
                     (email_key, ip_key, 1 if valid else 0, now))
        conn.execute("DELETE FROM auth_login_attempts WHERE attempted_at<?", (_utc_after(minutes=-1440),))
        if not valid:
            conn.commit()  # Persist failed attempts before returning the generic error.
            raise AuthenticationError("بيانات الدخول غير صحيحة")
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO auth_sessions (token_hash,user_id,expires_at,created_at) VALUES (?,?,?,?)",
                     (_session_digest(token), row["id"], _utc_after(days=SESSION_DAYS), now))
        return {"id": row["id"], "role": row["role"], "display_name": row["display_name"]}, token

def get_session_user(db_path: str, token: str) -> Optional[dict]:
    if not token or len(token) > 256:
        return None
    with connect(db_path) as conn:
        row = conn.execute(
            """SELECT u.id,u.role,u.display_name FROM auth_sessions s
               JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>? AND u.is_active=1""",
            (_session_digest(token), utc_now())).fetchone()
        return dict(row) if row else None

def revoke_session(db_path: str, token: str) -> bool:
    if not token or len(token) > 256:
        return False
    with connect(db_path) as conn:
        result = conn.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL",
                              (utc_now(), _session_digest(token)))
        return result.rowcount == 1


def allow_registration(db_path: str, ip_address: str) -> bool:
    ip_key = (ip_address or "unknown")[:64]
    now = utc_now()
    cutoff = _utc_after(minutes=-60)
    with connect(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM auth_registration_attempts WHERE ip_key=? AND attempted_at>=?",
            (ip_key, cutoff)
        ).fetchone()["n"]
        if count >= 5:
            return False
        conn.execute(
            "INSERT INTO auth_registration_attempts (ip_key,attempted_at) VALUES (?,?)",
            (ip_key, now)
        )
        conn.execute(
            "DELETE FROM auth_registration_attempts WHERE attempted_at<?",
            (_utc_after(minutes=-1440),)
        )
        return True
