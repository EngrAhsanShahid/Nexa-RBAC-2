from typing import Optional, List

from fastapi import Depends, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.custom_router import ProtectedRouter
from app.core.livekit import generate_subscriber_token
from app.db.session import get_db
from app.features.auth.models import PermissionEnum
from pymongo.database import Database

router = ProtectedRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class CameraStreamInfo(BaseModel):
    camera_id:   str
    tenant_id:   str
    source_path: Optional[str] = None
    enabled:     Optional[bool] = None
    livekit_url: str


class TokenResponse(BaseModel):
    token:       str
    livekit_url: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/cameras",
    response_model=List[CameraStreamInfo],
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def list_stream_cameras(
    tenant_id: str = Query(..., description="Tenant ID"),
    db: Database = Depends(get_db),
):
    """Get cameras for a tenant along with LiveKit URL."""
    cameras = list(db.cameras.find({"tenant_id": tenant_id}))
    livekit_url = get_settings().LIVEKIT_URL
    return [
        {
            "camera_id":   c.get("camera_id", ""),
            "tenant_id":   c.get("tenant_id", ""),
            "source_path": c.get("source_path"),
            "enabled":     c.get("enabled"),
            "livekit_url": livekit_url,
        }
        for c in cameras
    ]


@router.get(
    "/token",
    response_model=TokenResponse,
)
def get_stream_token(
    tenant_id: str = Query(..., description="Tenant ID"),
    camera_id: Optional[str] = Query(None, description="Camera ID (used as viewer identity)"),
    current_user: dict = Depends(ProtectedRouter.inject_current_user),
):
    """Get a LiveKit subscriber token for a tenant room."""
    viewer_id = camera_id or current_user.get("email", "viewer")
    token = generate_subscriber_token(tenant_id, viewer_id)
    return TokenResponse(
        token=token,
        livekit_url=get_settings().LIVEKIT_URL,
    )
