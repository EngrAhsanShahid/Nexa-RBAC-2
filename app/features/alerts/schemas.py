from typing import Optional, List, Literal

from pydantic import BaseModel


AlertPreset = Literal["today", "7d", "30d", "all", "custom"]
AlertSort = Literal["timestamp_desc", "timestamp_asc"]


class AlertRead(BaseModel):
    id: str
    alert_id: Optional[str] = None
    tenant_id: Optional[str] = None
    camera_id: Optional[str] = None
    frame_id: Optional[str] = None
    alert_type: Optional[str] = None
    label: Optional[str] = None
    pipeline_id: Optional[str] = None
    timestamp: Optional[float] = None
    date: Optional[str] = None
    time: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[float] = None
    details: Optional[dict] = None
    status: Optional[str] = None
    snapshot_path: Optional[str] = None
    clip_path: Optional[str] = None
    snapshot_url: Optional[str] = None
    clip_url: Optional[str] = None


class AlertsPagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool


class AlertsFilters(BaseModel):
    camera_id: Optional[str] = None
    preset: Optional[AlertPreset] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    search: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None


class AlertsPageResponse(BaseModel):
    items: List[AlertRead]
    pagination: AlertsPagination
    filters: AlertsFilters


class AlertsTimelineResponse(BaseModel):
    tenant_id: str
    camera_id: Optional[str] = None
    total: int
    high: int
    medium: int
    low: int