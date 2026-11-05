"""Authenticated InWork service marketplace API."""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from .auth import (
    AuthenticationError, get_session_user, initialize_auth_schema, login,
    register_user, revoke_session, _password_hash,
)
from .marketplace import (
    MarketplaceError, accept_request, cancel_request, create_request,
    get_request_contact, list_categories, list_user_requests,
    list_worker_requests, search_workers, share_request_contact,
    transition_request, update_worker_profile,
)

router = APIRouter(prefix="/v1", tags=["service-marketplace"])
DB_PATH = os.environ.get("INWORK_DB_PATH")


def initialize_api_database() -> None:
    from .marketplace import initialize_database
    initialize_database(DB_PATH)
    initialize_auth_schema(DB_PATH)


def _raise_domain(exc: Exception) -> None:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def require_same_origin(request: Request, x_inwork_request: Optional[str] = Header(None)) -> None:
    if x_inwork_request != "1":
        raise HTTPException(status_code=403, detail="طلب غير موثوق")
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        allowed = {item.strip().rstrip("/") for item in os.environ.get("INWORK_ALLOWED_ORIGINS", "").split(",") if item.strip()}
        same_origin = parsed.netloc == request.url.netloc and parsed.scheme == request.url.scheme
        if not same_origin and origin.rstrip("/") not in allowed:
            raise HTTPException(status_code=403, detail="مصدر الطلب غير مسموح")


def current_user(
    inwork_session: Optional[str] = Cookie(None),
    authorization: Optional[str] = Header(None),
) -> dict:
    token = inwork_session
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    user = get_session_user(DB_PATH, token or "")
    if not user:
        raise HTTPException(status_code=401, detail="سجّل الدخول أولًا")
    return user


def requester(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "requester":
        raise HTTPException(status_code=403, detail="هذه العملية لطالب الخدمة فقط")
    return user


def worker(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "worker":
        raise HTTPException(status_code=403, detail="هذه العملية لمقدم الخدمة فقط")
    return user


def admin(user: dict = Depends(current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="صلاحية الإدارة مطلوبة")
    return user


class RegisterInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    role: str
    category_id: Optional[int] = None


class LoginInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class RequestInput(BaseModel):
    category_id: int
    description: str = Field(min_length=5, max_length=2000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class WorkerProfileInput(BaseModel):
    bio: str = Field(default="", max_length=1000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    available: bool = True
    phone: Optional[str] = Field(default=None, max_length=32)
    whatsapp: Optional[str] = Field(default=None, max_length=32)


class StatusInput(BaseModel):
    status: str


class BootstrapInput(BaseModel):
    token: str = Field(min_length=24, max_length=256)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)


class CategoryInput(BaseModel):
    name_ar: str = Field(min_length=2, max_length=80)


@router.post("/auth/register")
def auth_register(data: RegisterInput, request: Request, response: Response,
                  _: None = Depends(require_same_origin)):
    try:
        user = register_user(DB_PATH, data.email, data.password, data.display_name,
                             data.role, data.category_id)
        session_user, token = login(DB_PATH, data.email, data.password,
                                    request.client.host if request.client else "unknown")
    except AuthenticationError as exc:
        _raise_domain(exc)
    response.set_cookie(
        "inwork_session", token, httponly=True, secure=request.url.scheme == "https",
        samesite=os.environ.get("INWORK_COOKIE_SAMESITE", "strict").lower(), max_age=7 * 24 * 60 * 60, path="/"
    )
    return {"user": session_user}


@router.post("/auth/login")
def auth_login(data: LoginInput, request: Request, response: Response,
               _: None = Depends(require_same_origin)):
    try:
        user, token = login(DB_PATH, data.email, data.password,
                            request.client.host if request.client else "unknown")
    except AuthenticationError as exc:
        _raise_domain(exc)
    response.set_cookie(
        "inwork_session", token, httponly=True, secure=request.url.scheme == "https",
        samesite="strict", max_age=7 * 24 * 60 * 60, path="/"
    )
    return {"user": user}


@router.post("/auth/logout")
def auth_logout(response: Response, user: dict = Depends(current_user),
                inwork_session: Optional[str] = Cookie(None),
                authorization: Optional[str] = Header(None),
                _: None = Depends(require_same_origin)):
    token = inwork_session or (authorization[7:].strip() if authorization and authorization.startswith("Bearer ") else "")
    revoke_session(DB_PATH, token or "")
    response.delete_cookie("inwork_session", path="/", httponly=True, samesite="strict")
    return {"ok": True}


@router.get("/auth/me")
def auth_me(user: dict = Depends(current_user)):
    return {"user": user}


@router.get("/categories")
def categories():
    return {"categories": list_categories(DB_PATH)}


@router.get("/workers/search")
def workers_search(category_id: int, latitude: float = Query(ge=-90, le=90),
                   longitude: float = Query(ge=-180, le=180), radius_km: float = Query(default=15, ge=1, le=100)):
    try:
        return {"workers": search_workers(DB_PATH, category_id, latitude, longitude, radius_km)}
    except MarketplaceError as exc:
        _raise_domain(exc)


@router.put("/worker/profile")
def worker_profile(data: WorkerProfileInput, user: dict = Depends(worker),
                   _: None = Depends(require_same_origin)):
    try:
        update_worker_profile(DB_PATH, user["id"], data.bio, data.latitude, data.longitude,
                              data.available, data.phone, data.whatsapp)
    except MarketplaceError as exc:
        _raise_domain(exc)
    return {"ok": True}


@router.get("/worker/requests")
def worker_requests(user: dict = Depends(worker)):
    try:
        return {"requests": list_worker_requests(DB_PATH, user["id"])}
    except MarketplaceError as exc:
        _raise_domain(exc)


@router.post("/requests")
def new_request(data: RequestInput, user: dict = Depends(requester),
                _: None = Depends(require_same_origin)):
    try:
        request_id = create_request(DB_PATH, user["id"], data.category_id, data.description,
                                    data.latitude, data.longitude)
        return {"id": request_id, "status": "open"}
    except MarketplaceError as exc:
        _raise_domain(exc)


@router.get("/requests/mine")
def my_requests(user: dict = Depends(current_user)):
    if user["role"] not in ("requester", "worker"):
        raise HTTPException(status_code=403, detail="صلاحية غير كافية")
    return {"requests": list_user_requests(DB_PATH, user["id"], user["role"])}


@router.post("/requests/{request_id}/accept")
def request_accept(request_id: int, user: dict = Depends(worker),
                   _: None = Depends(require_same_origin)):
    try:
        accepted = accept_request(DB_PATH, user["id"], request_id)
    except MarketplaceError as exc:
        _raise_domain(exc)
    if not accepted:
        raise HTTPException(status_code=409, detail="الطلب لم يعد متاحًا أو لا يطابق تخصصك")
    return {"id": request_id, "status": "accepted"}


@router.post("/requests/{request_id}/status")
def request_status(request_id: int, data: StatusInput, user: dict = Depends(worker),
                   _: None = Depends(require_same_origin)):
    try:
        changed = transition_request(DB_PATH, request_id, user["id"], data.status)
    except MarketplaceError as exc:
        _raise_domain(exc)
    if not changed:
        raise HTTPException(status_code=409, detail="لا يمكن تغيير حالة هذا الطلب")
    return {"id": request_id, "status": data.status}


@router.post("/requests/{request_id}/cancel")
def request_cancel(request_id: int, user: dict = Depends(requester),
                   _: None = Depends(require_same_origin)):
    if not cancel_request(DB_PATH, user["id"], request_id):
        raise HTTPException(status_code=409, detail="لا يمكن إلغاء هذا الطلب")
    return {"id": request_id, "status": "cancelled"}


@router.post("/requests/{request_id}/share-contact")
def request_share_contact(request_id: int, user: dict = Depends(requester),
                          _: None = Depends(require_same_origin)):
    if not share_request_contact(DB_PATH, user["id"], request_id):
        raise HTTPException(status_code=409, detail="يمكن مشاركة وسيلة الاتصال بعد قبول الطلب فقط")
    return {"ok": True, "contact_shared": True}


@router.get("/requests/{request_id}/contact")
def request_contact(request_id: int, user: dict = Depends(current_user)):
    contact = get_request_contact(DB_PATH, user["id"], user["role"], request_id)
    if not contact:
        raise HTTPException(status_code=403, detail="بيانات الاتصال غير متاحة قبل قبول الطلب وموافقة صاحبه")
    return {"contact": contact}


@router.post("/admin/bootstrap")
def admin_bootstrap(data: BootstrapInput, _: None = Depends(require_same_origin)):
    import hmac, secrets
    from .marketplace import connect, utc_now
    expected = os.environ.get("INWORK_ADMIN_BOOTSTRAP_TOKEN", "")
    if len(expected) < 24 or not hmac.compare_digest(data.token, expected):
        raise HTTPException(status_code=403, detail="رمز التهيئة غير صالح")
    user_id, now = secrets.token_urlsafe(18), utc_now()
    try:
        with connect(DB_PATH) as conn:
            conn.execute("BEGIN IMMEDIATE")
            if conn.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone():
                raise HTTPException(status_code=409, detail="تم إنشاء مدير النظام بالفعل")
            conn.execute("INSERT INTO users (id,role,display_name,created_at) VALUES (?,'admin',?,?)",
                         (user_id, data.display_name.strip(), now))
            conn.execute("INSERT INTO user_auth (user_id,email,password_hash,created_at) VALUES (?,?,?,?)",
                         (user_id, data.email.strip().lower(), _password_hash(data.password), now))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=409, detail="تعذر إنشاء حساب الإدارة") from exc
    return {"ok": True, "message": "تم إنشاء حساب الإدارة الأول. سجّل الدخول الآن."}


@router.post("/worker/subscription")
def worker_subscription(user: dict = Depends(worker), _: None = Depends(require_same_origin)):
    from .marketplace import connect, utc_now
    with connect(DB_PATH) as conn:
        active = conn.execute(
            "SELECT 1 FROM subscriptions WHERE worker_id=? AND status='active' AND starts_at<=? AND ends_at>=? LIMIT 1",
            (user["id"], utc_now(), utc_now())).fetchone()
        if active:
            raise HTTPException(status_code=409, detail="اشتراكك نشط بالفعل")
        cursor = conn.execute(
            "INSERT INTO subscriptions (worker_id,status,amount_egp,created_at) VALUES (?,'pending',100,?)",
            (user["id"], utc_now()))
        return {"subscription_id": cursor.lastrowid, "amount_egp": 100, "status": "pending"}


@router.post("/admin/subscriptions/{subscription_id}/verify")
def verify_subscription(subscription_id: int, user: dict = Depends(admin),
                         _: None = Depends(require_same_origin)):
    from .marketplace import connect, utc_now
    now = utc_now()
    end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(timespec="seconds")
    with connect(DB_PATH) as conn:
        pending = conn.execute(
            "SELECT worker_id FROM subscriptions WHERE id=? AND status='pending'",
            (subscription_id,)).fetchone()
        if not pending:
            raise HTTPException(status_code=404, detail="طلب الاشتراك غير موجود أو تمت مراجعته")
        conn.execute(
            "UPDATE subscriptions SET status='expired' WHERE worker_id=? AND status='active'",
            (pending["worker_id"],))
        conn.execute(
            "UPDATE subscriptions SET status='active',starts_at=?,ends_at=?,verified_by=?,verified_at=? WHERE id=?",
            (now, end, user["id"], now, subscription_id))
        conn.execute(
            "INSERT INTO admin_audit (admin_id,action,target_type,target_id,created_at) VALUES (?,?,?,?,?)",
            (user["id"], "verify_subscription", "subscription", str(subscription_id), now))
    return {"subscription_id": subscription_id, "status": "active", "ends_at": end}


@router.post("/admin/categories")
def create_category(data: CategoryInput, user: dict = Depends(admin),
                    _: None = Depends(require_same_origin)):
    from .marketplace import connect, utc_now
    try:
        with connect(DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO categories (name_ar, created_at) VALUES (?, ?)",
                (data.name_ar.strip(), utc_now())
            )
            return {"id": cursor.lastrowid, "name_ar": data.name_ar.strip()}
    except Exception as exc:
        raise HTTPException(status_code=409, detail="التخصص موجود بالفعل أو البيانات غير صالحة") from exc
