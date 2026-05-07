import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional, List

from bson import ObjectId
from fastapi import Query, Depends, HTTPException, status
from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database

from app.core.config import get_settings
from app.core.custom_router import ProtectedRouter
from app.core.minio import generate_presigned_url, normalize_object_path
from app.db.session import get_db
from app.features.auth.models import PermissionEnum
from app.features.alerts.schemas import (
    AlertRead,
    AlertsFilters,
    AlertsPageResponse,
    AlertsPagination,
    AlertPreset,
    AlertSort,
)

try:
    from fastapi_pagination import Params, create_page  # type: ignore[import-not-found]
except ImportError:
    class Params:
        def __init__(self, page: int = 1, size: int = 50):
            self.page = page
            self.size = size

    class _PageResult:
        def __init__(self, items, total: int, params: Params):
            self.items = items
            self.total = total
            self.page = params.page
            self.size = params.size
            self.pages = math.ceil(total / params.size) if total else 0

    def create_page(items, total: int, params: Params):
        return _PageResult(items, total, params)


router = ProtectedRouter()

_ALERT_INDEXES_READY = False


def _ensure_alert_indexes(db: Database) -> None:
    global _ALERT_INDEXES_READY
    if _ALERT_INDEXES_READY:
        return

    db.alerts.create_index([("tenant_id", ASCENDING), ("timestamp", DESCENDING)])
    db.alerts.create_index([("tenant_id", ASCENDING), ("camera_id", ASCENDING), ("timestamp", DESCENDING)])
    db.alerts.create_index([("tenant_id", ASCENDING), ("status", ASCENDING), ("timestamp", DESCENDING)])
    db.alerts.create_index([("tenant_id", ASCENDING), ("severity", ASCENDING), ("timestamp", DESCENDING)])
    _ALERT_INDEXES_READY = True

ALLOWED_PAGE_SIZES = {10, 25, 50}
ALLOWED_PRESETS = {"today", "7d", "30d", "all", "custom"}


def _presign_object_path(object_path: Optional[str], expires_in_seconds: Optional[int] = None) -> Optional[str]:
    if not object_path:
        return None

    try:
        url, _expires_in = generate_presigned_url(object_path, expires_in_seconds)
        return url
    except Exception:
        settings = get_settings()
        scheme = "https" if settings.MINIO_SECURE else "http"
        endpoint = settings.MINIO_ENDPOINT.rstrip("/")
        bucket = settings.MINIO_BUCKET.strip("/")
        object_name = normalize_object_path(object_path)
        return f"{scheme}://{endpoint}/{bucket}/{object_name}"


def _serialize_alert(
    doc: dict,
    *,
    use_alert_id_as_id: bool = False,
    expires_in_seconds: Optional[int] = None,
) -> dict:
    details = doc.get("details") or {}
    if not isinstance(details, dict):
        details = {}

    timestamp = doc.get("timestamp")
    alert_datetime = None
    if timestamp is not None:
        alert_datetime = datetime.fromtimestamp(float(timestamp), tz=timezone.utc)

    label = doc.get("label") or details.get("label")
    confidence = doc.get("confidence")
    if confidence is None:
        confidence = details.get("confidence")

    return {
        "id":            doc.get("alert_id") if use_alert_id_as_id and doc.get("alert_id") else str(doc["_id"]),
        "alert_id":      doc.get("alert_id"),
        "tenant_id":     doc.get("tenant_id"),
        "camera_id":     doc.get("camera_id"),
        "frame_id":      doc.get("frame_id"),
        "alert_type":    doc.get("alert_type"),
        "label":         label,
        "pipeline_id":   doc.get("pipeline_id"),
        "timestamp":     timestamp,
        "date":          alert_datetime.strftime("%Y-%m-%d") if alert_datetime else None,
        "time":          alert_datetime.strftime("%H:%M:%S") if alert_datetime else None,
        "severity":      doc.get("severity"),
        "confidence":    confidence,
        "details":       details,
        "status":        doc.get("status"),
        "snapshot_path": doc.get("snapshot_path"),
        "clip_path":     doc.get("clip_path"),
        "snapshot_url":  _presign_object_path(doc.get("snapshot_path"), expires_in_seconds),
        "clip_url":      _presign_object_path(doc.get("clip_path"), expires_in_seconds),
    }


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid date format: {value}") from exc


def _day_bounds(target_date: date) -> tuple[float, float]:
    start_dt = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1) - timedelta(microseconds=1)
    return start_dt.timestamp(), end_dt.timestamp()


def _resolve_date_window(
    preset: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str], str]:
    today = datetime.now(timezone.utc).date()

    effective_preset = preset or "today"
    if date_from or date_to:
        effective_preset = "custom"

    if effective_preset not in ALLOWED_PRESETS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid preset")

    if effective_preset == "all":
        return None, None, None, None, effective_preset

    if effective_preset == "custom":
        if not date_from or not date_to:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="date_from and date_to are required when preset=custom",
            )
        start_date = _parse_date(date_from)
        end_date = _parse_date(date_to)
    elif effective_preset == "today":
        start_date = today
        end_date = today
    elif effective_preset == "7d":
        start_date = today - timedelta(days=7)
        end_date = today
    elif effective_preset == "30d":
        start_date = today - timedelta(days=30)
        end_date = today
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid preset")

    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

    start_ts, _ = _day_bounds(start_date)
    _, end_ts = _day_bounds(end_date)
    return start_ts, end_ts, start_date.isoformat(), end_date.isoformat(), effective_preset


def _build_alert_query(
    tenant_id: str,
    camera_id: Optional[str],
    status_value: Optional[str],
    severity: Optional[str],
    search: Optional[str],
    preset: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
) -> tuple[dict, Optional[str], Optional[str], str]:
    start_ts, end_ts, effective_date_from, effective_date_to, effective_preset = _resolve_date_window(
        preset,
        date_from,
        date_to,
    )

    query: dict = {"tenant_id": tenant_id}
    if camera_id:
        query["camera_id"] = camera_id
    if status_value:
        query["status"] = status_value
    if severity:
        query["severity"] = severity
    if start_ts is not None and end_ts is not None:
        query["timestamp"] = {"$gte": start_ts, "$lte": end_ts}

    if search:
        term = search.strip()
        if term:
            escaped = re.escape(term)
            query["$or"] = [
                {"alert_type": {"$regex": escaped, "$options": "i"}},
                {"label": {"$regex": escaped, "$options": "i"}},
                {"details.label": {"$regex": escaped, "$options": "i"}},
                {"camera_id": {"$regex": escaped, "$options": "i"}},
                {"severity": {"$regex": escaped, "$options": "i"}},
                {"status": {"$regex": escaped, "$options": "i"}},
            ]

    return query, effective_date_from, effective_date_to, effective_preset


def _document_contains_reference(value, reference: str) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return any(_document_contains_reference(item, reference) for item in value.values())
    if isinstance(value, list):
        return any(_document_contains_reference(item, reference) for item in value)
    if isinstance(value, str):
        return reference == value or reference in value
    return reference == str(value)


def _find_alert_by_reference(db: Database, reference: str):
    candidates = [reference]
    if "_" in reference:
        suffix = reference.rsplit("_", 1)[-1]
        if suffix and suffix != reference:
            candidates.append(suffix)

    for candidate in candidates:
        alert = db.alerts.find_one({"alert_id": candidate})
        if alert:
            return alert

        alert = db.alerts.find_one({"id": candidate})
        if alert:
            return alert

        try:
            alert = db.alerts.find_one({"_id": ObjectId(candidate)})
            if alert:
                return alert
        except Exception:
            pass

    for alert in db.alerts.find({}):
        for candidate in candidates:
            if any(
                _document_contains_reference(alert.get(field), candidate)
                for field in ("alert_id", "tenant_id", "camera_id", "frame_id", "alert_type", "status", "snapshot_path", "clip_path")
            ):
                return alert
            if _document_contains_reference(alert, candidate):
                return alert

    return None


def _resolve_tenant_id(current_user: dict, tenant_id: Optional[str]) -> str:
    user_tenant_id = current_user.get("tenant_id") or current_user.get("tenantId")
    effective_tenant_id = tenant_id or user_tenant_id

    if not effective_tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tenant_id is required")

    if tenant_id and user_tenant_id and tenant_id != user_tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="tenant_id does not match authenticated user")

    return effective_tenant_id


@router.get(
    "/paginated",
    response_model=AlertsPageResponse,
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def list_alerts_paginated(
    tenant_id: Optional[str] = Query(None, description="Tenant ID (defaults to authenticated user's tenant)"),
    camera_id: Optional[str] = Query(None, description="Filter by camera_id"),
    preset: Optional[AlertPreset] = Query("today", description="today | 7d | 30d | all | custom"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD, used for custom ranges"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD, used for custom ranges"),
    search: Optional[str] = Query(None, description="Search alert_type, label, camera_id, severity, status, details.label"),
    status: Optional[str] = Query(None, description="Filter by alert status"),
    severity: Optional[str] = Query(None, description="Filter by severity (high/medium/low)"),
    expires_in_seconds: Optional[int] = Query(
        None,
        ge=1,
        description="Presigned URL lifetime in seconds for snapshot_url and clip_url",
    ),
    page: int = Query(1, ge=1, description="Page number starting at 1"),
    page_size: int = Query(10, ge=1, le=50, description="Page size: 10, 25, or 50"),
    sort: AlertSort = Query("timestamp_desc", description="timestamp_desc | timestamp_asc"),
    db: Database = Depends(get_db),
    current_user: dict = Depends(ProtectedRouter.inject_current_user),
):
    """
    Paginated alerts listing.

    Date handling uses UTC internally.
    - today: start of current UTC day through end of current UTC day
    - 7d / 30d: N days ago start of day through today end of day
    - custom: inclusive from date_from to date_to
    - all: no timestamp filter
    """
    if page_size not in ALLOWED_PAGE_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be one of 10, 25, or 50",
        )

    effective_tenant_id = _resolve_tenant_id(current_user, tenant_id)
    query, effective_date_from, effective_date_to, effective_preset = _build_alert_query(
        effective_tenant_id,
        camera_id,
        status,
        severity,
        search,
        preset,
        date_from,
        date_to,
    )

    _ensure_alert_indexes(db)

    sort_direction = DESCENDING if sort == "timestamp_desc" else ASCENDING
    total = db.alerts.count_documents(query)
    params = Params(page=page, size=page_size)
    cursor = (
        db.alerts.find(query)
        .sort([("timestamp", sort_direction), ("_id", sort_direction)])
        .skip((params.page - 1) * params.size)
        .limit(params.size)
    )
    items = [
        _serialize_alert(doc, use_alert_id_as_id=True, expires_in_seconds=expires_in_seconds)
        for doc in cursor
    ]

    page_result = create_page(items, total=total, params=params)

    pagination = AlertsPagination(
        page=page_result.page,
        page_size=page_result.size,
        total=page_result.total,
        total_pages=page_result.pages,
        has_next=page_result.page < page_result.pages,
        has_prev=page_result.page > 1 and page_result.pages > 0,
    )
    filters = AlertsFilters(
        camera_id=camera_id,
        preset=effective_preset,
        date_from=effective_date_from,
        date_to=effective_date_to,
        search=search,
        status=status,
        severity=severity,
    )

    return AlertsPageResponse(items=items, pagination=pagination, filters=filters)


@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def get_alert(
    alert_id: str,
    expires_in_seconds: Optional[int] = Query(
        None,
        ge=1,
        description="Presigned URL lifetime in seconds for snapshot_url and clip_url",
    ),
    db: Database = Depends(get_db),
):
    """Get a single alert by alert_id. Requires view_stream permission."""
    alert = _find_alert_by_reference(db, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return _serialize_alert(alert, expires_in_seconds=expires_in_seconds)


@router.get(
    "",
    response_model=List[AlertRead],
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def list_alerts(
    tenant_id: str = Query(..., description="Tenant ID"),
    camera_id: Optional[str] = Query(None, description="Filter by camera_id"),
    status: Optional[str] = Query(None, description="Filter by status (open/closed)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low/medium/high)"),
    expires_in_seconds: Optional[int] = Query(
        None,
        ge=1,
        description="Presigned URL lifetime in seconds for snapshot_url and clip_url",
    ),
    db: Database = Depends(get_db),
):
    """Get alerts for a tenant. Requires view_stream permission."""
    query = {"tenant_id": tenant_id}
    if camera_id:
        query["camera_id"] = camera_id
    if status:
        query["status"] = status
    if severity:
        query["severity"] = severity

    alerts = list(db.alerts.find(query).sort("timestamp", -1))
    return [_serialize_alert(a, expires_in_seconds=expires_in_seconds) for a in alerts]
