from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field

from app.features.auth.models import UserRole, PermissionEnum


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MfaLoginResponse(BaseModel):
    mfa_required: bool = True
    challenge_id: str
    message: str
    expires_in_seconds: int


class MfaVerifyRequest(BaseModel):
    challenge_id: str
    otp: str


class MfaVerifyResponse(Token):
    pass


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
    tenant_id:   Optional[str] = None
    created_at:  Optional[datetime] = None
    last_active: Optional[datetime] = None


class MeResponse(BaseModel):
    username: str
    role: str
    tenant_id: Optional[str] = None
    allowed_cameras: List[str] = Field(default_factory=list)
    email: Optional[EmailStr] = None
    created_at: Optional[datetime] = None


class MessageResponse(BaseModel):
    message: str


class UserCreate(BaseModel):
    email:     EmailStr
    full_name: Optional[str] = None
    password:  str
    role:      UserRole
    tenant_id: Optional[str] = None
    overrides: Optional[List[PermissionOverride]] = []


class UserUpdatePermissions(BaseModel):
    changes: List[PermissionOverride]