import hashlib
import secrets
import smtplib
import uuid
import ssl
from datetime import timedelta, datetime, timezone
from typing import Annotated
from email.message import EmailMessage

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo.database import Database
from pymongo import ASCENDING

from app.core.config import get_settings
from app.db.session import get_db
from app.features.auth import schemas
from app.features.auth.models import UserRole
from app.features.auth.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)

router   = APIRouter()
settings = get_settings()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


_MFA_INDEXES_READY = False


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def serialize_user(user: dict) -> dict:
    """Convert raw user document to frontend-compatible /me payload."""
    email = user.get("email", "")
    name = user.get("full_name") or ""
    tenant_id = user.get("tenant_id") or user.get("tenantId")
    allowed_cameras = user.get(
        "allowed_cameras") or user.get("allowedCameras") or []
    created_at = user.get("created_at")

    return {
        "username": name,
        "role": str(user.get("role", "")).lower(),
        "tenant_id": tenant_id,
        "allowed_cameras": allowed_cameras,
        "email": email,
        "createdAt": created_at,
        "created_at": created_at,
    }


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
        max_age=settings.COOKIE_MAX_AGE,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.COOKIE_NAME,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


def get_user_by_email(db: Database, email: str):
    return db.users.find_one({"email": email})


def authenticate_user(db: Database, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


def _ensure_mfa_indexes(db: Database) -> None:
    global _MFA_INDEXES_READY
    if _MFA_INDEXES_READY:
        return

    db.mfa_challenges.create_index([("challenge_id", ASCENDING)], unique=True)
    db.mfa_challenges.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.mfa_challenges.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    _MFA_INDEXES_READY = True


def _generate_otp() -> str:
    width = max(1, settings.MFA_OTP_LENGTH)
    return f"{secrets.randbelow(10 ** width):0{width}d}"


def _hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()


def _as_utc_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _send_otp_email(to_email: str, otp: str, full_name: str | None = None) -> None:
    if not settings.GMAIL_EMAIL or not settings.GMAIL_APP_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service is not configured",
        )

    greeting = f"Hi {full_name}," if full_name else "Hi,"
    text_body = (
        f"{greeting}\n\n"
        f"Your verification code is: {otp}\n\n"
        f"This code expires in {settings.MFA_OTP_EXPIRES_SECONDS // 60} minutes."
    )
    html_body = (
        f"<p>{greeting}</p>"
        f"<p>Your verification code is <strong>{otp}</strong>.</p>"
        f"<p>This code expires in {settings.MFA_OTP_EXPIRES_SECONDS // 60} minutes.</p>"
    )

    message = EmailMessage()
    message["Subject"] = "Your verification code"
    message["From"] = settings.GMAIL_FROM_EMAIL or settings.GMAIL_EMAIL
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.GMAIL_SMTP_HOST, settings.GMAIL_SMTP_PORT, context=context) as server:
            server.login(settings.GMAIL_EMAIL, settings.GMAIL_APP_PASSWORD)
            server.send_message(message)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gmail SMTP failed: {exc}",
        ) from exc


def _create_mfa_challenge(db: Database, user: dict) -> tuple[dict, str]:
    _ensure_mfa_indexes(db)
    challenge_id = uuid.uuid4().hex
    otp = _generate_otp()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.MFA_OTP_EXPIRES_SECONDS)

    challenge = {
        "challenge_id": challenge_id,
        "user_id": str(user["_id"]),
        "email": user.get("email"),
        "otp_hash": _hash_otp(otp),
        "created_at": now,
        "expires_at": expires_at,
    }
    db.mfa_challenges.insert_one(challenge)

    try:
        _send_otp_email(user.get("email", ""), otp, user.get("full_name"))
    except Exception:
        db.mfa_challenges.delete_one({"challenge_id": challenge_id})
        raise

    return challenge, otp


def _issue_token_response(user: dict, response: Response) -> schemas.Token:
    token = create_access_token(
        data={"sub": str(user["_id"]), "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    try:
        set_auth_cookie(response, token)
    except Exception:
        # Return the JWT even if a cookie cannot be attached in this environment.
        pass
    return schemas.Token(access_token=token)


def _validate_mfa_challenge(db: Database, challenge_id: str, otp: str) -> dict:
    _ensure_mfa_indexes(db)
    challenge = db.mfa_challenges.find_one({"challenge_id": challenge_id})
    if not challenge:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA code")

    now = datetime.now(timezone.utc)
    expires_at = _as_utc_datetime(challenge.get("expires_at"))
    if expires_at and expires_at < now:
        db.mfa_challenges.delete_one({"challenge_id": challenge_id})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA code")

    if challenge.get("otp_hash") != _hash_otp(otp):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA code")

    try:
        user = db.users.find_one({"_id": ObjectId(challenge["user_id"])})
    except Exception:
        db.mfa_challenges.delete_one({"challenge_id": challenge_id})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired MFA code")
    if not user or not user.get("is_active", True):
        db.mfa_challenges.delete_one({"challenge_id": challenge_id})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or non-existent user")

    db.mfa_challenges.delete_one({"challenge_id": challenge_id})
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_active": datetime.now(timezone.utc)}},
    )
    return user


# ──────────────────────────────────────────────
# Core auth dependencies
# ──────────────────────────────────────────────

async def get_current_user_ws(
    token: str,
) -> dict:
    """
    Validates the JWT and returns the full user document (dict).
    Also pre-loads role permissions into user["_role_permissions"]
    so RBAC checks don't need an extra DB call.
    """
    db = get_db()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(token)
    if not token_data or not token_data.user_id:
        print("Invalid token data")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.users.find_one({"_id": ObjectId(token_data.user_id)})
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or non-existent user",
        )

    # # Pre-load role permissions (avoids extra DB hit in every permission check)
    # role_doc = db.roles.find_one({"name": user["role"]}) or {}
    # user["_role_permissions"] = role_doc

    return user

def get_current_user(
    request: Request,
    db: Database = Depends(get_db),
    bearer_token: str = Depends(oauth2_scheme),
) -> dict:
    """
    Validates the JWT and returns the full user document (dict).
    Also pre-loads role permissions into user["_role_permissions"]
    so RBAC checks don't need an extra DB call.
    """
    token = request.cookies.get(settings.COOKIE_NAME) or bearer_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_access_token(token)
    if not token_data or not token_data.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.users.find_one({"_id": ObjectId(token_data.user_id)})
    if not user or not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive or non-existent user",
        )

    # Pre-load role permissions (avoids extra DB hit in every permission check)
    role_doc = db.roles.find_one({"name": user["role"]}) or {}
    user["_role_permissions"] = role_doc

    return user


def require_role(*roles: UserRole):
    """
    Dependency factory — restricts an endpoint to specific roles.

    Usage:
        dependencies=[Depends(require_role(UserRole.superadmin))]
        current_user = Depends(require_role(UserRole.superadmin, UserRole.admin))
    """
    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return current_user

    return dependency


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.post("/login", response_model=schemas.MfaLoginResponse)
def login(
    body: schemas.LoginRequest,
    db: Database = Depends(get_db),
):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    challenge, _otp = _create_mfa_challenge(db, user)
    return schemas.MfaLoginResponse(
        challenge_id=challenge["challenge_id"],
        message="Verification code sent to your email",
        expires_in_seconds=settings.MFA_OTP_EXPIRES_SECONDS,
    )


# Swagger UI Authorize button ke liye (form-data)
@router.post("/token", response_model=schemas.MfaLoginResponse, include_in_schema=False)
def token_form(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Database = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    challenge, _otp = _create_mfa_challenge(db, user)
    return schemas.MfaLoginResponse(
        challenge_id=challenge["challenge_id"],
        message="Verification code sent to your email",
        expires_in_seconds=settings.MFA_OTP_EXPIRES_SECONDS,
    )


@router.post("/verify-mfa", response_model=schemas.Token)
def verify_mfa(
    body: schemas.MfaVerifyRequest,
    response: Response,
    db: Database = Depends(get_db),
):
    user = _validate_mfa_challenge(db, body.challenge_id, body.otp)
    return _issue_token_response(user, response)


@router.get("/me", response_model=schemas.MeResponse)
def me(current_user: dict = Depends(get_current_user)):
    return serialize_user(current_user)


@router.post("/logout", response_model=schemas.MessageResponse)
def logout(response: Response):
    clear_auth_cookie(response)
    return schemas.MessageResponse(message="Logged out successfully")