"""
Seed script — populates roles and default users.

Usage:
    cd camera_rbac
    pip install -r requirements.txt
    python seed_data.py
"""

from datetime import datetime, timezone

from app.db.session import get_db
from app.features.auth.models import PermissionEnum, UserRole
from app.features.auth.security import get_password_hash

db = get_db()


# ──────────────────────────────────────────────
# Roles  (default permission matrix)
# ──────────────────────────────────────────────

def seed_roles():
    db.roles.drop()

    roles = [
        {
            "name": UserRole.superadmin.value,
            # Superadmin — everything ON
            PermissionEnum.add_camera.value:         True,
            PermissionEnum.delete_camera.value:      True,
            PermissionEnum.view_stream.value:        True,
            PermissionEnum.add_tenant.value:         True,
            PermissionEnum.delete_tenant.value:      True,
            PermissionEnum.manage_users.value:       True,
            PermissionEnum.manage_permissions.value: True,
        },
        {
            "name": UserRole.admin.value,
            # Admin — can manage cameras & tenants, NOT users/permissions
            PermissionEnum.add_camera.value:         True,
            PermissionEnum.delete_camera.value:      True,
            PermissionEnum.view_stream.value:        True,
            PermissionEnum.add_tenant.value:         True,
            PermissionEnum.delete_tenant.value:      True,
            PermissionEnum.manage_users.value:       False,
            PermissionEnum.manage_permissions.value: False,
        },
        {
            "name": UserRole.user.value,
            # User — can only view streams
            PermissionEnum.add_camera.value:         False,
            PermissionEnum.delete_camera.value:      False,
            PermissionEnum.view_stream.value:        True,
            PermissionEnum.add_tenant.value:         False,
            PermissionEnum.delete_tenant.value:      False,
            PermissionEnum.manage_users.value:       False,
            PermissionEnum.manage_permissions.value: False,
        },
    ]

    db.roles.insert_many(roles)
    print("✅ Roles seeded")


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────

def seed_users():
    db.users.drop()

    now = datetime.now(timezone.utc)
    users = [
        {
            "email":               "superadmin@example.com",
            "full_name":           "Super Admin",
            "hashed_password":     get_password_hash("superadmin123"),
            "role":                UserRole.superadmin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
        },
        {
            "email":               "admin@example.com",
            "full_name":           "Admin User",
            "hashed_password":     get_password_hash("admin123"),
            "role":                UserRole.admin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
        },
        {
            "email":               "user@example.com",
            "full_name":           "Regular User",
            "hashed_password":     get_password_hash("user123"),
            "role":                UserRole.user.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
        },
    ]

    db.users.insert_many(users)
    print("✅ Users seeded")


# ──────────────────────────────────────────────
# Cameras
# ──────────────────────────────────────────────

def seed_cameras():
    db.cameras.drop()

    cameras = [
        {
            "tenant_id":         "tenant_001",
            "camera_id":         "cam_001",
            "source_path":       "rtsp://192.168.1.101:554/stream1",
            "loop":              False,
            "target_fps":        10,
            "pipelines":         ["motion_detection", "object_detection"],
            "enabled":           True,
            "record_full_video": "false",
        },
        {
            "tenant_id":         "tenant_001",
            "camera_id":         "cam_002",
            "source_path":       "rtsp://192.168.1.102:554/stream1",
            "loop":              False,
            "target_fps":        15,
            "pipelines":         ["face_recognition"],
            "enabled":           True,
            "record_full_video": "true",
        },
        {
            "tenant_id":         "tenant_002",
            "camera_id":         "cam_003",
            "source_path":       "rtsp://10.0.0.50:554/live",
            "loop":              False,
            "target_fps":        10,
            "pipelines":         ["motion_detection"],
            "enabled":           False,
            "record_full_video": "false",
        },
    ]

    db.cameras.insert_many(cameras)
    print("✅ Cameras seeded")


# ──────────────────────────────────────────────
# Alerts
# ──────────────────────────────────────────────

def seed_alerts():
    db.alerts.drop()

    now = datetime.now(timezone.utc).timestamp()

    alerts = [
        {
            "alert_id":      "alert_001",
            "tenant_id":     "tenant_001",
            "camera_id":     "cam_001",
            "frame_id":      "frame_0001",
            "alert_type":    "motion_detected",
            "timestamp":     now - 3600,
            "severity":      "low",
            "confidence":    0.82,
            "pipeline_id":   "motion_detection",
            "details":       {"region": "zone_A", "pixel_change": 12.5},
            "status":        "open",
            "snapshot_path": "tenant_001/cam_001/snapshots/frame_0001.jpg",
            "clip_path":     None,
        },
        {
            "alert_id":      "alert_002",
            "tenant_id":     "tenant_001",
            "camera_id":     "cam_002",
            "frame_id":      "frame_0240",
            "alert_type":    "face_recognized",
            "timestamp":     now - 1800,
            "severity":      "medium",
            "confidence":    0.95,
            "pipeline_id":   "face_recognition",
            "details":       {"person_id": "unknown", "match_score": 0.95},
            "status":        "open",
            "snapshot_path": "tenant_001/cam_002/snapshots/frame_0240.jpg",
            "clip_path":     "tenant_001/cam_002/clips/clip_0240.mp4",
        },
        {
            "alert_id":      "alert_003",
            "tenant_id":     "tenant_002",
            "camera_id":     "cam_003",
            "frame_id":      "frame_0512",
            "alert_type":    "intrusion_detected",
            "timestamp":     now - 600,
            "severity":      "high",
            "confidence":    0.91,
            "pipeline_id":   "motion_detection",
            "details":       {"region": "perimeter", "object_count": 2},
            "status":        "closed",
            "snapshot_path": "tenant_002/cam_003/snapshots/frame_0512.jpg",
            "clip_path":     "tenant_002/cam_003/clips/clip_0512.mp4",
        },
    ]

    db.alerts.insert_many(alerts)
    print("✅ Alerts seeded")


if __name__ == "__main__":
    seed_roles()
    seed_users()
    seed_cameras()
    seed_alerts()
    print("✅ All data seeded successfully!")
    print()
    print("Login credentials:")
    print("  superadmin@example.com / superadmin123")
    print("  admin@example.com      / admin123")
    print("  user@example.com       / user123")
