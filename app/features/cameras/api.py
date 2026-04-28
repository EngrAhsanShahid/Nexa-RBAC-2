from bson import ObjectId
from fastapi import Depends, HTTPException
from pymongo.database import Database

from app.core.custom_router import ProtectedRouter
from app.db.session import get_db
from app.features.auth.models import PermissionEnum
from app.features.cameras.schemas import CameraCreate, CameraRead

router = ProtectedRouter()


def _serialize_camera(doc: dict) -> dict:
    return {
        "id":                str(doc["_id"]),
        "tenant_id":         doc.get("tenant_id"),
        "camera_id":         doc.get("camera_id"),
        "source_path":       doc.get("source_path"),
        "loop":              doc.get("loop"),
        "target_fps":        doc.get("target_fps"),
        "pipelines":         doc.get("pipelines"),
        "enabled":           doc.get("enabled"),
        "record_full_video": doc.get("record_full_video"),
    }


@router.get(
    "",
    response_model=list[CameraRead],
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def list_cameras(db: Database = Depends(get_db)):
    """List all cameras. Requires view_stream permission."""
    cameras = list(db.cameras.find())
    return [_serialize_camera(c) for c in cameras]


@router.get(
    "/{camera_id}",
    response_model=CameraRead,
    dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)],
)
def get_camera(camera_id: str, db: Database = Depends(get_db)):
    """Get a single camera by camera_id field. Requires view_stream permission."""
    camera = db.cameras.find_one({"camera_id": camera_id})
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return _serialize_camera(camera)


@router.post(
    "",
    response_model=CameraRead,
)
def add_camera(
    camera: CameraCreate,
    db: Database = Depends(get_db),
    current_user: dict = ProtectedRouter.requires_permission(PermissionEnum.add_camera),
):
    """Add a new camera. Requires add_camera permission."""
    doc = {
        **camera.model_dump(),
        "added_by": current_user.get("email"),
    }
    result = db.cameras.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize_camera(doc)


@router.delete("/{camera_id}")
def delete_camera(
    camera_id: str,
    db: Database = Depends(get_db),
    current_user: dict = ProtectedRouter.requires_permission(PermissionEnum.delete_camera),
):
    """Delete a camera. Requires delete_camera permission."""
    result = db.cameras.delete_one({"_id": ObjectId(camera_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"detail": f"Camera {camera_id} deleted by {current_user.get('email')}"}
