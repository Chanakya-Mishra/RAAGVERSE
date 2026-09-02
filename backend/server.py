"""Bandish - Backend API
FastAPI + Motor (MongoDB) + JWT auth + Resend OTP.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import io
import csv
import asyncio
import logging
import secrets
import bcrypt
import jwt
import requests
import resend
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, status, UploadFile, File, Form, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid

# ---------- Config ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("music_club")

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 60 * 12  # 12 hours
REFRESH_TOKEN_DAYS = 7
OTP_EXPIRY_MINUTES = 10
BRUTE_FORCE_LIMIT = 5
BRUTE_FORCE_WINDOW_MIN = 15

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

# ---------- Emergent Object Storage ----------
STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
APP_NAME = os.environ.get("APP_NAME", "music-club")
storage_key: Optional[str] = None

ALLOWED_GOOGLE_ADMINS = {
    e.strip().lower() for e in os.environ.get("ALLOWED_GOOGLE_ADMIN_EMAILS", "").split(",") if e.strip()
}

MIME_MAP = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
ALLOWED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024  # 8 MB


def init_storage(force: bool = False) -> Optional[str]:
    global storage_key
    if storage_key and not force:
        return storage_key
    if not EMERGENT_KEY:
        return None
    try:
        r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
        r.raise_for_status()
        storage_key = r.json()["storage_key"]
        return storage_key
    except Exception as e:
        logger.error(f"init_storage failed: {e}")
        return None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Object storage not initialized")
    r = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if r.status_code == 404:
        key = init_storage(force=True)
        r = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    r.raise_for_status()
    return r.json()


def get_object(path: str) -> tuple[bytes, str]:
    key = init_storage()
    if not key:
        raise HTTPException(status_code=500, detail="Object storage not initialized")
    r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if r.status_code == 404:
        key = init_storage(force=True)
        r = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    r.raise_for_status()
    return r.content, r.headers.get("Content-Type", "application/octet-stream")

# ---------- Helpers ----------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": now_utc() + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": now_utc() + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def _cookie_kwargs(max_age: int) -> dict:
    return {
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "max_age": max_age,
        "path": "/",
    }


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, **_cookie_kwargs(ACCESS_TOKEN_MINUTES * 60))
    response.set_cookie("refresh_token", refresh, **_cookie_kwargs(REFRESH_TOKEN_DAYS * 86400))


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")


def user_public(u: dict) -> dict:
    return {
        "id": u["id"],
        "email": u["email"],
        "name": u.get("name", ""),
        "role": u.get("role", "member"),
        "status": u.get("status", "active"),
        "instrument": u.get("instrument"),
        "bio": u.get("bio"),
        "created_at": u.get("created_at"),
    }


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ---------- Email ----------
async def send_otp_email(recipient: str, name: str, otp: str) -> dict:
    subject = "Bandish - Password Reset OTP"
    html = f"""
    <table width='100%' cellpadding='0' cellspacing='0' style='background:#0B0C10;padding:32px 0;font-family:Arial,sans-serif;'>
      <tr><td align='center'>
        <table width='560' cellpadding='0' cellspacing='0' style='background:#12141C;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;color:#FFFFFF;'>
          <tr><td>
            <h1 style='margin:0 0 8px 0;font-size:24px;color:#F97316;letter-spacing:-0.5px;'>Bandish</h1>
            <p style='margin:0 0 24px 0;font-size:13px;color:#94A3B8;'>Password Reset Request</p>
            <p style='margin:0 0 16px 0;font-size:15px;line-height:1.6;'>Hey {name or 'there'},</p>
            <p style='margin:0 0 24px 0;font-size:15px;line-height:1.6;color:#CBD5E1;'>Use the one-time passcode below to reset your password. It expires in <strong style='color:#F97316;'>10 minutes</strong>.</p>
            <div style='background:linear-gradient(135deg,#F97316 0%,#EF4444 50%,#A855F7 100%);padding:2px;border-radius:12px;margin:0 0 24px 0;'>
              <div style='background:#0B0C10;border-radius:10px;padding:24px;text-align:center;'>
                <div style='font-size:38px;font-weight:800;letter-spacing:12px;color:#FFFFFF;font-family:monospace;'>{otp}</div>
              </div>
            </div>
            <p style='margin:0 0 8px 0;font-size:13px;color:#94A3B8;line-height:1.6;'>If you didn't request this, you can safely ignore this email. Your password stays unchanged.</p>
            <hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:32px 0 16px 0;'/>
            <p style='margin:0;font-size:12px;color:#64748B;'>Bandish · Express Yourself.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    if not resend.api_key:
        logger.warning(f"[DEV MODE] Resend not configured. OTP for {recipient}: {otp}")
        return {"ok": False, "error": "resend_not_configured"}
    try:
        params = {"from": SENDER_EMAIL, "to": [recipient], "subject": subject, "html": html}
        result = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"OTP email sent to {recipient} id={result.get('id') if isinstance(result, dict) else result}")
        return {"ok": True, "error": None}
    except Exception as e:
        msg = str(e)
        logger.error(f"Resend send failed for {recipient}: {msg}. OTP={otp}")
        return {"ok": False, "error": msg}


# ---------- Models ----------
class LoginBody(BaseModel):
    email: EmailStr
    password: str


class ForgotBody(BaseModel):
    email: EmailStr


class VerifyOtpBody(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)


class ResetPasswordBody(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=6)


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6)


class MemberCreate(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=6)
    instrument: Optional[str] = None
    bio: Optional[str] = None
    status: Literal["active", "pending", "inactive"] = "active"


class MemberUpdate(BaseModel):
    name: Optional[str] = None
    instrument: Optional[str] = None
    bio: Optional[str] = None
    status: Optional[Literal["active", "pending", "inactive"]] = None
    password: Optional[str] = None


class EventCreate(BaseModel):
    title: str
    description: str
    event_type: Literal["Jam", "Workshop", "Open Mic", "Concert"]
    date: str  # ISO datetime string
    location: str = "Jam Room #2"
    capacity: int = 40
    image_url: Optional[str] = None
    published: bool = True


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[Literal["Jam", "Workshop", "Open Mic", "Concert"]] = None
    date: Optional[str] = None
    location: Optional[str] = None
    capacity: Optional[int] = None
    image_url: Optional[str] = None
    published: Optional[bool] = None


class SessionCreate(BaseModel):
    title: str
    facilitator: str
    session_type: Literal["Jam Session", "Vocal Workshop", "Instrument Workshop", "Production", "Rehearsal"]
    week: int = Field(ge=1, le=52)
    date: str
    duration_minutes: int = 90
    notes: Optional[str] = None


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    facilitator: Optional[str] = None
    session_type: Optional[str] = None
    week: Optional[int] = None
    date: Optional[str] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None


class GalleryCreate(BaseModel):
    caption: str
    image_url: str
    tag: Literal["Jams", "Concerts", "Workshops", "Open Mic"] = "Jams"
    photographer: Optional[str] = None


class GalleryUpdate(BaseModel):
    caption: Optional[str] = None
    image_url: Optional[str] = None
    tag: Optional[Literal["Jams", "Concerts", "Workshops", "Open Mic"]] = None
    photographer: Optional[str] = None


class MemberInviteBody(BaseModel):
    email: EmailStr
    name: str
    instrument: Optional[str] = None


class RSVPBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    guests: int = Field(default=1, ge=1, le=10)


class GoogleCallbackBody(BaseModel):
    session_id: str


class SponsorCreate(BaseModel):
    name: str
    tagline: Optional[str] = None
    website_url: Optional[str] = None
    logo_url: Optional[str] = None
    tier: Literal["Gold", "Silver", "Bronze", "Community"] = "Community"
    order: int = 100
    active: bool = True


class SponsorUpdate(BaseModel):
    name: Optional[str] = None
    tagline: Optional[str] = None
    website_url: Optional[str] = None
    logo_url: Optional[str] = None
    tier: Optional[Literal["Gold", "Silver", "Bronze", "Community"]] = None
    order: Optional[int] = None
    active: Optional[bool] = None


# ---------- App ----------
app = FastAPI(title="Bandish API")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/")
async def root():
    return {"message": "Bandish API", "status": "online"}


# ---------- Auth Routes ----------
async def _check_lockout(identifier: str) -> None:
    doc = await db.login_attempts.find_one({"identifier": identifier})
    if not doc:
        return
    if doc.get("count", 0) >= BRUTE_FORCE_LIMIT:
        last = doc.get("last_attempt")
        if isinstance(last, str):
            last = datetime.fromisoformat(last)
        if last and (now_utc() - last) < timedelta(minutes=BRUTE_FORCE_WINDOW_MIN):
            raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")
        await db.login_attempts.delete_one({"identifier": identifier})


async def _record_failed(identifier: str) -> None:
    await db.login_attempts.update_one(
        {"identifier": identifier},
        {"$inc": {"count": 1}, "$set": {"last_attempt": now_utc().isoformat()}},
        upsert=True,
    )


async def _clear_attempts(identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


@api.post("/auth/login")
async def login(body: LoginBody, request: Request, response: Response):
    email = body.email.lower().strip()
    identifier = email  # Rate-limit by email regardless of proxy IP
    await _check_lockout(identifier)

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        await _record_failed(identifier)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user.get("status") == "inactive":
        raise HTTPException(status_code=403, detail="Account is inactive")

    await _clear_attempts(identifier)
    access = create_access_token(user["id"], user["email"], user.get("role", "member"))
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": user_public(user), "access_token": access}


@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"success": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user_public(user)}


@api.post("/auth/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        access = create_access_token(user["id"], user["email"], user.get("role", "member"))
        response.set_cookie("access_token", access, **_cookie_kwargs(ACCESS_TOKEN_MINUTES * 60))
        return {"access_token": access}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@api.post("/auth/forgot-password")
async def forgot_password(body: ForgotBody):
    email = body.email.lower().strip()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    delivered = True
    # Always respond same shape (do not leak enumeration), but only generate OTP if user exists.
    if user:
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = hash_password(otp)
        send_result = await send_otp_email(email, user.get("name", ""), otp)
        delivered = bool(send_result.get("ok"))
        await db.password_reset_otps.update_one(
            {"email": email},
            {"$set": {
                "email": email,
                "otp_hash": otp_hash,
                # Store plaintext ONLY when Resend delivery failed, so admin can share it manually
                # (needed while Resend is in sandbox mode without a verified domain).
                "otp_plain": None if delivered else otp,
                "delivery_status": "sent" if delivered else "failed",
                "delivery_error": None if delivered else (send_result.get("error") or "")[:400],
                "expires_at": (now_utc() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
                "used": False,
                "attempts": 0,
                "created_at": now_utc().isoformat(),
                "user_name": user.get("name", ""),
                "user_role": user.get("role", "member"),
            }},
            upsert=True,
        )
    return {
        "success": True,
        "delivered": delivered,
        "message": (
            "If an account exists for this email, an OTP has been sent."
            if delivered
            else "OTP generated but email delivery failed. Please contact an admin to retrieve your code."
        ),
    }


async def _validate_otp(email: str, otp: str, consume: bool = False) -> dict:
    rec = await db.password_reset_otps.find_one({"email": email}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=400, detail="No OTP requested for this email")
    if rec.get("used"):
        raise HTTPException(status_code=400, detail="OTP already used")
    if rec.get("attempts", 0) >= 6:
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new OTP.")
    expires_at = rec.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if not expires_at or expires_at < now_utc():
        raise HTTPException(status_code=400, detail="OTP expired. Request a new one.")
    if not verify_password(otp, rec["otp_hash"]):
        await db.password_reset_otps.update_one({"email": email}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if consume:
        await db.password_reset_otps.update_one({"email": email}, {"$set": {"used": True}})
    return rec


@api.post("/auth/verify-otp")
async def verify_otp(body: VerifyOtpBody):
    await _validate_otp(body.email.lower().strip(), body.otp)
    return {"success": True, "message": "OTP verified"}


@api.post("/auth/reset-password")
async def reset_password(body: ResetPasswordBody):
    email = body.email.lower().strip()
    await _validate_otp(email, body.otp, consume=True)
    new_hash = hash_password(body.new_password)
    result = await db.users.update_one({"email": email}, {"$set": {"password_hash": new_hash}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "Password updated. Please log in with your new password."}


@api.post("/auth/change-password")
async def change_password(body: ChangePasswordBody, user: dict = Depends(get_current_user)):
    if not verify_password(body.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    await db.users.update_one({"id": user["id"]}, {"$set": {"password_hash": hash_password(body.new_password)}})
    return {"success": True}


# ---------- Members ----------
@api.get("/members")
async def list_members(admin: dict = Depends(require_admin)):
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(1000)
    return {"members": docs}


@api.post("/members")
async def create_member(body: MemberCreate, admin: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": body.name,
        "password_hash": hash_password(body.password),
        "role": "member",
        "status": body.status,
        "instrument": body.instrument,
        "bio": body.bio,
        "created_at": now_utc().isoformat(),
    }
    await db.users.insert_one(doc)
    return {"member": {k: v for k, v in doc.items() if k not in ("password_hash", "_id")}}


@api.put("/members/{member_id}")
async def update_member(member_id: str, body: MemberUpdate, admin: dict = Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if "password" in updates:
        updates["password_hash"] = hash_password(updates.pop("password"))
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    result = await db.users.update_one({"id": member_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    doc = await db.users.find_one({"id": member_id}, {"_id": 0, "password_hash": 0})
    return {"member": doc}


@api.delete("/members/{member_id}")
async def delete_member(member_id: str, admin: dict = Depends(require_admin)):
    target = await db.users.find_one({"id": member_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if target.get("role") == "admin":
        raise HTTPException(status_code=403, detail="Cannot delete an admin account")
    await db.users.delete_one({"id": member_id})
    return {"success": True}


# ---------- Generic CRUD for events/sessions/gallery ----------
def _crud_endpoints(name: str, coll_name: str, CreateModel, UpdateModel, sort_field: str = "created_at"):
    coll = db[coll_name]

    @api.get(f"/public/{name}")
    async def public_list():
        query = {"published": True} if name == "events" else {}
        docs = await coll.find(query, {"_id": 0}).sort(sort_field, -1).to_list(500)
        return {name: docs}

    @api.get(f"/{name}")
    async def admin_list(admin: dict = Depends(require_admin)):
        docs = await coll.find({}, {"_id": 0}).sort(sort_field, -1).to_list(500)
        return {name: docs}

    @api.post(f"/{name}")
    async def create(body: CreateModel, admin: dict = Depends(require_admin)):
        doc = body.model_dump()
        doc["id"] = str(uuid.uuid4())
        doc["created_at"] = now_utc().isoformat()
        doc["created_by"] = admin["id"]
        insert_doc = dict(doc)
        await coll.insert_one(insert_doc)
        return {"item": doc}

    @api.put(f"/{name}/{{item_id}}")
    async def update(item_id: str, body: UpdateModel, admin: dict = Depends(require_admin)):
        updates = body.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        updates["updated_at"] = now_utc().isoformat()
        result = await coll.update_one({"id": item_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"{name} not found")
        doc = await coll.find_one({"id": item_id}, {"_id": 0})
        return {"item": doc}

    @api.delete(f"/{name}/{{item_id}}")
    async def delete(item_id: str, admin: dict = Depends(require_admin)):
        result = await coll.delete_one({"id": item_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"{name} not found")
        return {"success": True}

    # Rename functions to avoid FastAPI collision
    public_list.__name__ = f"public_list_{name}"
    admin_list.__name__ = f"admin_list_{name}"
    create.__name__ = f"create_{name}"
    update.__name__ = f"update_{name}"
    delete.__name__ = f"delete_{name}"


_crud_endpoints("events", "events", EventCreate, EventUpdate, sort_field="date")
_crud_endpoints("sessions", "sessions", SessionCreate, SessionUpdate, sort_field="date")
_crud_endpoints("gallery", "gallery", GalleryCreate, GalleryUpdate, sort_field="created_at")


# ---------- Google OAuth (Emergent Auth) — Admins Only ----------
# REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
@api.post("/auth/google/callback")
async def google_callback(body: GoogleCallbackBody, response: Response):
    try:
        r = requests.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.error(f"Google session-data failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google session")

    email = (data.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=401, detail="No email on Google profile")
    if email not in ALLOWED_GOOGLE_ADMINS:
        raise HTTPException(status_code=403, detail="This Google account is not authorized for admin access")

    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        # Should already be seeded, but guard anyway
        user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": data.get("name") or "Admin",
            "password_hash": hash_password(secrets.token_urlsafe(16)),
            "role": "admin",
            "status": "active",
            "created_at": now_utc().isoformat(),
        }
        await db.users.insert_one(dict(user))
    else:
        await db.users.update_one({"email": email}, {"$set": {"role": "admin", "status": "active", "picture": data.get("picture")}})

    access = create_access_token(user["id"], user["email"], "admin")
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    return {"user": user_public(user), "access_token": access}


# ---------- Gallery Upload (Object Storage) ----------
@api.post("/gallery/upload")
async def gallery_upload(
    file: UploadFile = File(...),
    caption: str = Form(...),
    tag: str = Form("Jams"),
    photographer: str = Form(""),
    admin: dict = Depends(require_admin),
):
    if file.content_type not in ALLOWED_UPLOAD_TYPES:
        raise HTTPException(status_code=400, detail="Only JPG, PNG, or WEBP images are allowed")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 8 MB limit")
    if tag not in {"Jams", "Concerts", "Workshops", "Open Mic"}:
        tag = "Jams"

    ext = (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg").lower()
    if ext not in MIME_MAP:
        ext = "jpg"
    path = f"{APP_NAME}/gallery/{admin['id']}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, file.content_type or MIME_MAP[ext])
    stored_path = result["path"]
    image_url = f"/api/files/{stored_path}"

    doc = {
        "id": str(uuid.uuid4()),
        "caption": caption,
        "image_url": image_url,
        "storage_path": stored_path,
        "tag": tag,
        "photographer": photographer or admin.get("name"),
        "content_type": file.content_type,
        "size": len(data),
        "is_deleted": False,
        "created_at": now_utc().isoformat(),
        "created_by": admin["id"],
    }
    await db.gallery.insert_one(dict(doc))
    doc.pop("_id", None)
    return {"item": doc}


@api.get("/files/{path:path}")
async def serve_file(path: str):
    # Gallery images are meant to be public. Ensure the file is a known, non-deleted gallery item.
    record = await db.gallery.find_one({"storage_path": path, "is_deleted": {"$ne": True}}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    data, content_type = get_object(path)
    return Response(content=data, media_type=record.get("content_type", content_type))


# ---------- Member Invite + Bulk Import ----------
async def _send_invite_email(email: str, name: str, password: str) -> None:
    subject = "You're in — Bandish"
    login_url = os.environ.get("PUBLIC_APP_URL", "")
    html = f"""
    <table width='100%' cellpadding='0' cellspacing='0' style='background:#0B0C10;padding:32px 0;font-family:Arial,sans-serif;'>
      <tr><td align='center'>
        <table width='560' cellpadding='0' cellspacing='0' style='background:#12141C;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;color:#FFFFFF;'>
          <tr><td>
            <h1 style='margin:0 0 8px 0;font-size:24px;color:#F97316;letter-spacing:-0.5px;'>Bandish</h1>
            <p style='margin:0 0 24px 0;font-size:13px;color:#94A3B8;'>You're invited</p>
            <p style='margin:0 0 16px 0;font-size:15px;line-height:1.6;'>Hey {name or 'there'},</p>
            <p style='margin:0 0 16px 0;font-size:15px;line-height:1.6;color:#CBD5E1;'>Your Bandish membership is ready. Use these credentials to sign in and RSVP to jams, workshops, and open mics.</p>
            <div style='background:#0B0C10;border:1px solid rgba(249,115,22,0.3);border-radius:10px;padding:16px 20px;margin:0 0 20px 0;font-family:monospace;color:#FFFFFF;'>
              <div style='font-size:12px;color:#94A3B8;'>Email</div>
              <div style='font-size:15px;margin-bottom:8px;'>{email}</div>
              <div style='font-size:12px;color:#94A3B8;'>Temporary password</div>
              <div style='font-size:15px;'>{password}</div>
            </div>
            <p style='margin:0 0 20px 0;font-size:13px;color:#94A3B8;'>Please change this password after your first login.</p>
            <hr style='border:none;border-top:1px solid rgba(255,255,255,0.08);margin:32px 0 16px 0;'/>
            <p style='margin:0;font-size:12px;color:#64748B;'>Bandish · Express Yourself.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    if not resend.api_key:
        logger.warning(f"[DEV] Invite for {email} — password: {password}")
        return
    try:
        await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [email], "subject": subject, "html": html})
    except Exception as e:
        logger.error(f"Invite email send failed for {email}: {e}")


@api.post("/members/invite")
async def invite_member(body: MemberInviteBody, admin: dict = Depends(require_admin)):
    email = body.email.lower().strip()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Email already registered")
    temp_password = secrets.token_urlsafe(9)
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "name": body.name,
        "password_hash": hash_password(temp_password),
        "role": "member",
        "status": "active",
        "instrument": body.instrument,
        "bio": None,
        "invited_by": admin["id"],
        "created_at": now_utc().isoformat(),
    }
    await db.users.insert_one(dict(doc))
    await _send_invite_email(email, body.name, temp_password)
    return {"member": {k: v for k, v in doc.items() if k not in ("password_hash", "_id")}, "invited": True}


@api.post("/members/bulk")
async def bulk_import_members(
    file: UploadFile = File(...),
    send_invite: bool = Form(False),
    admin: dict = Depends(require_admin),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    raw = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(raw))
    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        try:
            email = (row.get("email") or "").strip().lower()
            name = (row.get("name") or "").strip()
            instrument = (row.get("instrument") or "").strip() or None
            if not email or not name:
                errors.append(f"Row {i}: missing email or name")
                continue
            if await db.users.find_one({"email": email}):
                skipped += 1
                continue
            temp_password = secrets.token_urlsafe(9)
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "name": name,
                "password_hash": hash_password(temp_password),
                "role": "member",
                "status": "active",
                "instrument": instrument,
                "bio": None,
                "created_at": now_utc().isoformat(),
                "invited_by": admin["id"],
            })
            created += 1
            if send_invite:
                await _send_invite_email(email, name, temp_password)
        except Exception as e:
            errors.append(f"Row {i}: {e}")
    return {"created": created, "skipped_existing": skipped, "errors": errors}


# ---------- Event RSVPs (with Waitlist) ----------
def _rsvp_doc(event_id: str, name: str, email: str, guests: int, user_id: Optional[str] = None, rsvp_status: str = "confirmed") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "event_id": event_id,
        "user_id": user_id,
        "name": name,
        "email": email.lower().strip(),
        "guests": guests,
        "status": rsvp_status,
        "created_at": now_utc().isoformat(),
    }


async def _get_event_or_404(event_id: str) -> dict:
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def _confirmed_seats(event_id: str) -> int:
    agg = await db.rsvps.aggregate([
        {"$match": {"event_id": event_id, "status": "confirmed"}},
        {"$group": {"_id": None, "total": {"$sum": "$guests"}}},
    ]).to_list(1)
    return agg[0]["total"] if agg else 0


async def _waitlist_position(event_id: str, rsvp_id: str) -> int:
    docs = await db.rsvps.find({"event_id": event_id, "status": "waitlisted"}, {"id": 1}).sort("created_at", 1).to_list(2000)
    for i, d in enumerate(docs, start=1):
        if d.get("id") == rsvp_id:
            return i
    return 0


async def _resolve_status(event: dict, adding: int) -> str:
    if not event.get("capacity"):
        return "confirmed"
    used = await _confirmed_seats(event["id"])
    return "confirmed" if (used + adding) <= event["capacity"] else "waitlisted"


async def _promote_waitlist(event: dict) -> None:
    """Fill any freed capacity from the front of the waitlist and email the promoted RSVPs."""
    if not event.get("capacity"):
        return
    while True:
        used = await _confirmed_seats(event["id"])
        room = event["capacity"] - used
        if room <= 0:
            return
        next_wait = await db.rsvps.find_one(
            {"event_id": event["id"], "status": "waitlisted", "guests": {"$lte": room}},
            sort=[("created_at", 1)],
        )
        if not next_wait:
            return
        await db.rsvps.update_one({"id": next_wait["id"]}, {"$set": {"status": "confirmed", "promoted_at": now_utc().isoformat()}})
        asyncio.create_task(_send_promoted_email(next_wait, event))


async def _send_promoted_email(rsvp: dict, event: dict) -> None:
    subject = f"You're in — {event['title']}"
    html = f"""
    <table width='100%' cellpadding='0' cellspacing='0' style='background:#0B0C10;padding:32px 0;font-family:Arial,sans-serif;'>
      <tr><td align='center'>
        <table width='560' cellpadding='0' cellspacing='0' style='background:#12141C;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;color:#FFFFFF;'>
          <tr><td>
            <h1 style='margin:0 0 8px 0;font-size:24px;color:#F97316;letter-spacing:-0.5px;'>Bandish</h1>
            <p style='margin:0 0 24px 0;font-size:13px;color:#94A3B8;'>Waitlist Promoted</p>
            <p style='margin:0 0 16px 0;font-size:15px;line-height:1.6;'>Hey {rsvp.get('name') or 'there'},</p>
            <p style='margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#CBD5E1;'>Great news — a seat opened up for <strong style='color:#F97316;'>{event['title']}</strong> and we bumped you off the waitlist. You're confirmed.</p>
            <div style='background:#0B0C10;border:1px solid rgba(249,115,22,0.3);border-radius:10px;padding:16px 20px;margin:0 0 20px 0;color:#FFFFFF;'>
              <div style='font-size:12px;color:#94A3B8;'>When</div>
              <div style='font-size:15px;margin-bottom:8px;'>{datetime.fromisoformat(event['date']).strftime('%A · %b %d · %I:%M %p') if isinstance(event.get('date'), str) else event.get('date')}</div>
              <div style='font-size:12px;color:#94A3B8;'>Where</div>
              <div style='font-size:15px;'>{event.get('location', 'Jam Room #2')}</div>
            </div>
            <p style='margin:0;font-size:12px;color:#64748B;'>Bandish · Express Yourself.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    if not resend.api_key:
        logger.warning(f"[DEV] Promoted RSVP for {rsvp['email']} to {event['title']}")
        return
    try:
        await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [rsvp["email"]], "subject": subject, "html": html})
    except Exception as e:
        logger.error(f"Promoted email failed for {rsvp['email']}: {e}")


async def _send_event_reminder(rsvp: dict, event: dict) -> None:
    when = event.get("date", "")
    try:
        when_str = datetime.fromisoformat(when).strftime("%A · %b %d · %I:%M %p") if isinstance(when, str) else str(when)
    except Exception:
        when_str = str(when)
    subject = f"Tomorrow: {event['title']}"
    html = f"""
    <table width='100%' cellpadding='0' cellspacing='0' style='background:#0B0C10;padding:32px 0;font-family:Arial,sans-serif;'>
      <tr><td align='center'>
        <table width='560' cellpadding='0' cellspacing='0' style='background:#12141C;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:40px;color:#FFFFFF;'>
          <tr><td>
            <h1 style='margin:0 0 8px 0;font-size:24px;color:#F97316;letter-spacing:-0.5px;'>Bandish</h1>
            <p style='margin:0 0 24px 0;font-size:13px;color:#94A3B8;'>Reminder · See you tomorrow</p>
            <p style='margin:0 0 12px 0;font-size:15px;line-height:1.6;'>Hey {rsvp.get('name') or 'there'},</p>
            <p style='margin:0 0 20px 0;font-size:15px;line-height:1.6;color:#CBD5E1;'>Just a nudge — you're locked in for <strong style='color:#F97316;'>{event['title']}</strong>. Bring your instrument, your voice, or just your ears.</p>
            <div style='background:#0B0C10;border:1px solid rgba(249,115,22,0.3);border-radius:10px;padding:16px 20px;margin:0 0 20px 0;'>
              <div style='font-size:12px;color:#94A3B8;'>When</div>
              <div style='font-size:15px;margin-bottom:8px;'>{when_str}</div>
              <div style='font-size:12px;color:#94A3B8;'>Where</div>
              <div style='font-size:15px;'>{event.get('location', 'Jam Room #2')}</div>
            </div>
            <p style='margin:0 0 8px 0;font-size:13px;color:#94A3B8;'>Need to cancel? Log in to your member dashboard and drop your RSVP so someone on the waitlist can grab your spot.</p>
            <p style='margin:16px 0 0 0;font-size:12px;color:#64748B;'>Bandish · Express Yourself.</p>
          </td></tr>
        </table>
      </td></tr>
    </table>
    """
    if not resend.api_key:
        logger.warning(f"[DEV] Reminder for {rsvp['email']} — {event['title']}")
        return
    try:
        await asyncio.to_thread(resend.Emails.send, {"from": SENDER_EMAIL, "to": [rsvp["email"]], "subject": subject, "html": html})
    except Exception as e:
        logger.error(f"Reminder email failed for {rsvp['email']}: {e}")


async def _dispatch_reminders() -> dict:
    """Find confirmed RSVPs for events in the next 12–36 hours that haven't been reminded yet."""
    now = now_utc()
    lower = (now + timedelta(hours=12)).isoformat()
    upper = (now + timedelta(hours=36)).isoformat()
    events = await db.events.find({"date": {"$gte": lower, "$lte": upper}, "published": True}, {"_id": 0}).to_list(500)
    sent = 0
    for ev in events:
        rsvps = await db.rsvps.find({"event_id": ev["id"], "status": "confirmed", "reminder_sent_at": {"$exists": False}}, {"_id": 0}).to_list(2000)
        for r in rsvps:
            await _send_event_reminder(r, ev)
            await db.rsvps.update_one({"id": r["id"]}, {"$set": {"reminder_sent_at": now.isoformat()}})
            sent += 1
    return {"events_checked": len(events), "reminders_sent": sent, "window": {"from": lower, "to": upper}}


async def _reminder_loop():
    """Runs forever; checks for reminders every 30 minutes."""
    while True:
        try:
            result = await _dispatch_reminders()
            if result["reminders_sent"]:
                logger.info(f"Reminder loop: {result}")
        except Exception as e:
            logger.error(f"Reminder loop error: {e}")
        await asyncio.sleep(30 * 60)


@api.post("/public/events/{event_id}/rsvp")
async def public_rsvp(event_id: str, body: RSVPBody):
    event = await _get_event_or_404(event_id)
    if not event.get("published", True):
        raise HTTPException(status_code=404, detail="Event not found")
    existing = await db.rsvps.find_one({"event_id": event_id, "email": body.email.lower().strip()})
    if existing:
        raise HTTPException(status_code=409, detail="You've already RSVP'd for this event with this email")
    status_val = await _resolve_status(event, body.guests)
    doc = _rsvp_doc(event_id, body.name, body.email, body.guests, rsvp_status=status_val)
    await db.rsvps.insert_one(dict(doc))
    doc.pop("_id", None)
    if status_val == "waitlisted":
        doc["waitlist_position"] = await _waitlist_position(event_id, doc["id"])
    return {"rsvp": doc}


@api.post("/events/{event_id}/rsvp")
async def member_rsvp(event_id: str, user: dict = Depends(get_current_user)):
    event = await _get_event_or_404(event_id)
    existing = await db.rsvps.find_one({"event_id": event_id, "user_id": user["id"]})
    if existing:
        raise HTTPException(status_code=409, detail="Already RSVP'd")
    status_val = await _resolve_status(event, 1)
    doc = _rsvp_doc(event_id, user["name"], user["email"], 1, user_id=user["id"], rsvp_status=status_val)
    await db.rsvps.insert_one(dict(doc))
    doc.pop("_id", None)
    if status_val == "waitlisted":
        doc["waitlist_position"] = await _waitlist_position(event_id, doc["id"])
    return {"rsvp": doc}


@api.delete("/events/{event_id}/rsvp")
async def cancel_member_rsvp(event_id: str, user: dict = Depends(get_current_user)):
    result = await db.rsvps.delete_one({"event_id": event_id, "user_id": user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="No RSVP found")
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if event:
        await _promote_waitlist(event)
    return {"success": True}


@api.delete("/events/{event_id}/rsvps/{rsvp_id}")
async def admin_delete_rsvp(event_id: str, rsvp_id: str, admin: dict = Depends(require_admin)):
    result = await db.rsvps.delete_one({"id": rsvp_id, "event_id": event_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="RSVP not found")
    event = await db.events.find_one({"id": event_id}, {"_id": 0})
    if event:
        await _promote_waitlist(event)
    return {"success": True}


@api.get("/events/{event_id}/rsvps")
async def list_event_rsvps(event_id: str, admin: dict = Depends(require_admin)):
    event = await _get_event_or_404(event_id)
    all_docs = await db.rsvps.find({"event_id": event_id}, {"_id": 0}).sort("created_at", 1).to_list(2000)
    confirmed = [d for d in all_docs if d.get("status", "confirmed") == "confirmed"]
    waitlisted = [d for d in all_docs if d.get("status") == "waitlisted"]
    total = sum(d.get("guests", 1) for d in confirmed)
    return {
        "rsvps": all_docs,
        "confirmed": confirmed,
        "waitlisted": waitlisted,
        "total_seats": total,
        "capacity": event.get("capacity"),
        "waitlist_count": len(waitlisted),
    }


@api.get("/me/rsvps")
async def my_rsvps(user: dict = Depends(get_current_user)):
    docs = await db.rsvps.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for r in docs:
        ev = await db.events.find_one({"id": r["event_id"]}, {"_id": 0})
        r["event"] = ev
        if r.get("status") == "waitlisted":
            r["waitlist_position"] = await _waitlist_position(r["event_id"], r["id"])
    return {"rsvps": docs}


@api.get("/public/events/{event_id}/rsvp-count")
async def public_rsvp_count(event_id: str):
    total = await _confirmed_seats(event_id)
    waitlist = await db.rsvps.count_documents({"event_id": event_id, "status": "waitlisted"})
    event = await db.events.find_one({"id": event_id}, {"_id": 0}) or {}
    return {"total": total, "waitlist": waitlist, "capacity": event.get("capacity")}


@api.post("/admin/send-reminders")
async def trigger_reminders(admin: dict = Depends(require_admin)):
    return await _dispatch_reminders()


# ---------- Admin: view undelivered OTPs (fallback while Resend has no verified domain) ----------
@api.get("/admin/pending-otps")
async def admin_pending_otps(admin: dict = Depends(require_admin)):
    """Return currently valid password-reset OTPs whose email delivery failed.
    Lets admins hand the code to the member directly until a domain is verified in Resend."""
    now = now_utc()
    docs = await db.password_reset_otps.find(
        {"used": False, "delivery_status": "failed"},
        {"_id": 0, "otp_hash": 0},
    ).sort("created_at", -1).to_list(100)
    active = []
    for d in docs:
        exp = d.get("expires_at")
        if isinstance(exp, str):
            try:
                exp_dt = datetime.fromisoformat(exp)
            except Exception:
                continue
            if exp_dt < now:
                continue
        d["expires_at"] = exp
        active.append(d)
    return {"pending": active}


@api.post("/admin/otps/{email}/resend")
async def admin_resend_otp(email: str, admin: dict = Depends(require_admin)):
    """Force-resend the OTP email for a member. Useful after verifying a Resend domain."""
    email = email.lower().strip()
    rec = await db.password_reset_otps.find_one({"email": email, "used": False}, {"_id": 0})
    if not rec or not rec.get("otp_plain"):
        raise HTTPException(status_code=404, detail="No re-sendable OTP for this email")
    result = await send_otp_email(email, rec.get("user_name", ""), rec["otp_plain"])
    delivered = bool(result.get("ok"))
    await db.password_reset_otps.update_one(
        {"email": email},
        {"$set": {"delivery_status": "sent" if delivered else "failed", "delivery_error": None if delivered else (result.get("error") or "")[:400]}},
    )
    return {"success": True, "delivered": delivered, "error": result.get("error")}


# ---------- Sponsors ----------
@api.get("/public/sponsors")
async def public_sponsors():
    docs = await db.sponsors.find({"active": True}, {"_id": 0}).sort([("order", 1), ("created_at", -1)]).to_list(200)
    return {"sponsors": docs}


@api.get("/sponsors")
async def list_sponsors(admin: dict = Depends(require_admin)):
    docs = await db.sponsors.find({}, {"_id": 0}).sort([("order", 1), ("created_at", -1)]).to_list(500)
    return {"sponsors": docs}


@api.post("/sponsors")
async def create_sponsor(body: SponsorCreate, admin: dict = Depends(require_admin)):
    doc = body.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = now_utc().isoformat()
    doc["created_by"] = admin["id"]
    await db.sponsors.insert_one(dict(doc))
    return {"item": doc}


@api.put("/sponsors/{sponsor_id}")
async def update_sponsor(sponsor_id: str, body: SponsorUpdate, admin: dict = Depends(require_admin)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    updates["updated_at"] = now_utc().isoformat()
    result = await db.sponsors.update_one({"id": sponsor_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    doc = await db.sponsors.find_one({"id": sponsor_id}, {"_id": 0})
    return {"item": doc}


@api.delete("/sponsors/{sponsor_id}")
async def delete_sponsor(sponsor_id: str, admin: dict = Depends(require_admin)):
    result = await db.sponsors.delete_one({"id": sponsor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    return {"success": True}


# ---------- Stats ----------
@api.get("/admin/stats")
async def admin_stats(admin: dict = Depends(require_admin)):
    return {
        "members": await db.users.count_documents({"role": "member"}),
        "admins": await db.users.count_documents({"role": "admin"}),
        "events": await db.events.count_documents({}),
        "sessions": await db.sessions.count_documents({}),
        "gallery": await db.gallery.count_documents({"is_deleted": {"$ne": True}}),
        "rsvps": await db.rsvps.count_documents({"status": "confirmed"}),
        "waitlist": await db.rsvps.count_documents({"status": "waitlisted"}),
        "sponsors": await db.sponsors.count_documents({"active": True}),
    }


app.include_router(api)


# ---------- Startup ----------
@app.on_event("startup")
async def on_startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.password_reset_otps.create_index("email", unique=True)
    await db.login_attempts.create_index("identifier")
    for coll in ("events", "sessions", "gallery"):
        await db[coll].create_index("id", unique=True)
    await db.rsvps.create_index("id", unique=True)
    await db.rsvps.create_index([("event_id", 1), ("email", 1)])
    await db.rsvps.create_index([("event_id", 1), ("user_id", 1)])
    await db.rsvps.create_index([("event_id", 1), ("status", 1), ("created_at", 1)])
    await db.sponsors.create_index("id", unique=True)

    # Warm up object storage
    try:
        if init_storage():
            logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Object storage init failed: {e}")

    # Kick off background reminder loop
    asyncio.create_task(_reminder_loop())

    admins = [
        (os.environ["ADMIN1_EMAIL"], os.environ["ADMIN1_NAME"], os.environ["ADMIN1_PASSWORD"]),
        (os.environ["ADMIN2_EMAIL"], os.environ["ADMIN2_NAME"], os.environ["ADMIN2_PASSWORD"]),
    ]
    for email, name, password in admins:
        email = email.lower().strip()
        existing = await db.users.find_one({"email": email})
        if not existing:
            await db.users.insert_one({
                "id": str(uuid.uuid4()),
                "email": email,
                "name": name,
                "password_hash": hash_password(password),
                "role": "admin",
                "status": "active",
                "created_at": now_utc().isoformat(),
            })
            logger.info(f"Seeded admin {email}")
        elif not verify_password(password, existing.get("password_hash", "")):
            await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password), "role": "admin", "status": "active"}})
            logger.info(f"Re-synced admin password for {email}")

    # Seed a couple of demo events/sessions if empty
    if await db.events.count_documents({}) == 0:
        seed_events = [
            {"id": str(uuid.uuid4()), "title": "Semester Kick-Off Jam", "description": "Open jam night to welcome new members with acoustic sets and improv rounds.", "event_type": "Jam", "date": (now_utc() + timedelta(days=7)).isoformat(), "location": "Jam Room #2", "capacity": 60, "image_url": "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?w=800", "published": True, "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "title": "Open Mic Night", "description": "Take the mic, drop a poem, cover a track, or debut originals.", "event_type": "Open Mic", "date": (now_utc() + timedelta(days=21)).isoformat(), "location": "Amphitheatre", "capacity": 120, "image_url": "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?w=800", "published": True, "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "title": "Annual Campus Concert", "description": "The grand finale - full stage production with lights, bands, and headliners.", "event_type": "Concert", "date": (now_utc() + timedelta(days=70)).isoformat(), "location": "Main Quad", "capacity": 500, "image_url": "https://images.unsplash.com/photo-1600779547877-be592ef5aad3?w=800", "published": True, "created_at": now_utc().isoformat()},
        ]
        await db.events.insert_many(seed_events)

    if await db.sessions.count_documents({}) == 0:
        seed_sessions = [
            {"id": str(uuid.uuid4()), "title": "Acoustic Ice-Breaker Jam", "facilitator": "Chanakya", "session_type": "Jam Session", "week": 1, "date": (now_utc() + timedelta(days=3)).isoformat(), "duration_minutes": 90, "notes": "Bring your instrument or just show up to sing along.", "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "title": "Vocal Warm-Up Clinic", "facilitator": "Siddharth", "session_type": "Vocal Workshop", "week": 2, "date": (now_utc() + timedelta(days=10)).isoformat(), "duration_minutes": 60, "notes": "Breath control, range, and pitch drills.", "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "title": "DAW Production Basics", "facilitator": "Chanakya", "session_type": "Production", "week": 4, "date": (now_utc() + timedelta(days=24)).isoformat(), "duration_minutes": 120, "notes": "Intro to Ableton / FL Studio - bring laptops.", "created_at": now_utc().isoformat()},
        ]
        await db.sessions.insert_many(seed_sessions)

    if await db.gallery.count_documents({}) == 0:
        seed_gallery = [
            {"id": str(uuid.uuid4()), "caption": "Late-night jam in Jam Room #2", "image_url": "https://images.unsplash.com/photo-1598488035139-bdbb2231ce04?w=800", "tag": "Jams", "photographer": "Chanakya", "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "caption": "Open Mic energy", "image_url": "https://images.unsplash.com/photo-1499364615650-ec38552f4f34?w=800", "tag": "Open Mic", "photographer": "Siddharth", "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "caption": "Guitar close-up", "image_url": "https://images.unsplash.com/photo-1605340406960-f5b496c38b3d?w=800", "tag": "Workshops", "photographer": "Chanakya", "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "caption": "Campus Concert night", "image_url": "https://images.unsplash.com/photo-1600779547877-be592ef5aad3?w=800", "tag": "Concerts", "photographer": "Siddharth", "created_at": now_utc().isoformat()},
        ]
        await db.gallery.insert_many(seed_gallery)

    if await db.sponsors.count_documents({}) == 0:
        seed_sponsors = [
            {"id": str(uuid.uuid4()), "name": "Campus FM", "tagline": "Student radio partner", "website_url": "https://example.com", "logo_url": "", "tier": "Gold", "order": 10, "active": True, "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "name": "Riff & Roast", "tagline": "Fuel for late-night jams", "website_url": "https://example.com", "logo_url": "", "tier": "Silver", "order": 20, "active": True, "created_at": now_utc().isoformat()},
            {"id": str(uuid.uuid4()), "name": "Strings Bazaar", "tagline": "Instrument rentals & repairs", "website_url": "https://example.com", "logo_url": "", "tier": "Bronze", "order": 30, "active": True, "created_at": now_utc().isoformat()},
        ]
        await db.sponsors.insert_many(seed_sponsors)


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
