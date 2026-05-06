from typing import Optional, List
from fastapi import Query, Depends, HTTPException, status
from bson import ObjectId
from pymongo.database import Database
from pydantic import BaseModel

from app.core.custom_router import ProtectedRouter
from app.db.session import get_db
from app.features.auth.models import PermissionEnum


router = ProtectedRouter()


class AlertRead(BaseModel):
    id:            str
    alert_id:      Optional[str] = None
    tenant_id:     Optional[str] = None
    camera_id:     Optional[str] = None
    frame_id:      Optional[str] = None
    alert_type:    Optional[str] = None
    timestamp:     Optional[float] = None
    severity:      Optional[str] = None
    confidence:    Optional[float] = None
    pipeline_id:   Optional[str] = None
    details:       Optional[dict] = None
    status:        Optional[str] = None
    snapshot_path: Optional[str] = None
    clip_path:     Optional[str] = None


def _serialize_alert(doc: dict) -> dict:
    return {
        "id":            str(doc["_id"]),
        "alert_id":      doc.get("alert_id"),
        "tenant_id":     doc.get("tenant_id"),
        "camera_id":     doc.get("camera_id"),
        "frame_id":      doc.get("frame_id"),
        "alert_type":    doc.get("alert_type"),
        "timestamp":     doc.get("timestamp"),
        "severity":      doc.get("severity"),
        "confidence":    doc.get("confidence"),
        "pipeline_id":   doc.get("pipeline_id"),
        "details":       doc.get("details"),
        "status":        doc.get("status"),
        "snapshot_path": doc.get("snapshot_path"),
        "clip_path":     doc.get("clip_path"),
    }


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


@router.get(
    "/{alert_id}",
    response_model=AlertRead,
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def get_alert(
    alert_id: str,
    db: Database = Depends(get_db),
):
    """Get a single alert by alert_id. Requires view_stream permission."""
    alert = _find_alert_by_reference(db, alert_id)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    return _serialize_alert(alert)


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
    return [_serialize_alert(a) for a in alerts]
