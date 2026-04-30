from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ── Media (clips / images stored in MinIO) ──────────────────────────────────

class MediaRead(BaseModel):
    object_path:  str               # path inside MinIO bucket
    media_type:   str               # "clip" or "image"
    uploaded_by:  Optional[str] = None
    uploaded_at:  Optional[datetime] = None


class MediaUrlResponse(BaseModel):
    url:        str
    expires_in: int                 # seconds


# ── Cameras ──────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    tenant_id:         str
    camera_id:         str
    source_path:       str
    loop:              bool = False
    target_fps:        int = 10
    pipelines:         List[str] = []
    enabled:           bool = True
    record_full_video: str = "false"


class CameraUpdate(BaseModel):
    source_path:       Optional[str] = None
    loop:              Optional[bool] = None
    target_fps:        Optional[int] = None
    pipelines:         Optional[List[str]] = None
    enabled:           Optional[bool] = None
    record_full_video: Optional[str] = None


class CameraRead(BaseModel):
    id:                str
    tenant_id:         Optional[str] = None
    camera_id:         Optional[str] = None
    source_path:       Optional[str] = None
    loop:              Optional[bool] = None
    target_fps:        Optional[int] = None
    pipelines:         Optional[List[str]] = None
    enabled:           Optional[bool] = None
    record_full_video: Optional[str] = None
