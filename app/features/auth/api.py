from datetime import timedelta, datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo.database import Database

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
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def serialize_user(user: dict) -> dict:
    """Convert a raw MongoDB user document to a safe API-serialisable dict."""
    return {
        "id":          str(user["_id"]),
        "email":       user["email"],
        "full_name":   user.get("full_name"),
        "role":        user["role"],
        "is_active":   user.get("is_active", True),
        "created_at":  user.get("created_at"),
        "last_active": user.get("last_active"),
    }


def get_user_by_email(db: Database, email: str):
    return db.users.find_one({"email": email})


def authenticate_user(db: Database, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


# ──────────────────────────────────────────────
# Core auth dependencies
# ──────────────────────────────────────────────

def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Database = Depends(get_db),
) -> dict:
    """
    Validates the JWT and returns the full user document (dict).
    Also pre-loads role permissions into user["_role_permissions"]
    so RBAC checks don't need an extra DB call.
    """
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

@router.post("/login", response_model=schemas.Token)
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

    token = create_access_token(
        data={"sub": str(user["_id"]), "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_active": datetime.now(timezone.utc)}},
    )
    return schemas.Token(access_token=token)


# Swagger UI Authorize button ke liye (form-data)
@router.post("/token", response_model=schemas.Token, include_in_schema=False)
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
    token = create_access_token(
        data={"sub": str(user["_id"]), "role": user["role"]},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_active": datetime.now(timezone.utc)}},
    )
    return schemas.Token(access_token=token)


@router.get("/me", response_model=schemas.UserRead)
def me(current_user: dict = Depends(get_current_user)):
    return serialize_user(current_user)
