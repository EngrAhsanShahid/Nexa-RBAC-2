from typing import List, Optional

from pydantic import BaseModel


class CameraCreate(BaseModel):
    tenant_id:         str
    camera_id:         str
    source_path:       str
    loop:              bool = False
    target_fps:        int = 10
    pipelines:         List[str] = []
    enabled:           bool = True
    record_full_video: str = "false"


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
