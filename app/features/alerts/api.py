from typing import Optional, List
from fastapi import Query, Depends
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
