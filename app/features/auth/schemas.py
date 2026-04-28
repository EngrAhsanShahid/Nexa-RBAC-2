from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr

from app.features.auth.models import UserRole, PermissionEnum


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None
    role:    Optional[str] = None


class PermissionOverride(BaseModel):
    permission_name: PermissionEnum
    value: bool


class UserRead(BaseModel):
    id:          str
    email:       str
    full_name:   Optional[str] = None
    role:        UserRole
    is_active:   bool
    created_at:  Optional[datetime] = None
    last_active: Optional[datetime] = None


class UserCreate(BaseModel):
    email:     EmailStr
    full_name: Optional[str] = None
    password:  str
    role:      UserRole
    overrides: Optional[List[PermissionOverride]] = []


class UserUpdatePermissions(BaseModel):
    changes: List[PermissionOverride]
