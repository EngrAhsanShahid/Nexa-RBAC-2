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
            "email":               "m.hussain7006@gmail.com",
            "full_name":           "Muhammad Hussain",
            "hashed_password":     get_password_hash("superadmin123"),
            "role":                UserRole.superadmin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
            "tenant_id":           "tenant_01",  # Superadmin can access all tenants
        },
        {
            "email":               "husain@lambdatheta.com",
            "full_name":           "Husain Ahmed",
            "hashed_password":     get_password_hash("admin123"),
            "role":                UserRole.admin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
            "tenant_id":           "tenant_01",  # Admin can access tenant_01
        },
        {
            "email":               "ahsanshahid2010@hotmail.com",
            "full_name":           "Ahsan Shahid",
            "hashed_password":     get_password_hash("ahsan123"),
            "role":                UserRole.admin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
            "tenant_id":           "tenant_01",  # Admin can access tenant_01
        }, 
        {
            "email":               "anas2024lt@gmail.com",
            "full_name":           "Anas Shaikh",
            "hashed_password":     get_password_hash("anas123"),
            "role":                UserRole.admin.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
            "tenant_id":           "tenant_01",  # Admin can access tenant_01
        },            
        {
            "email":               "ahsanshahid2010.as@gmail.com",
            "full_name":           "Ahsan Shahid",
            "hashed_password":     get_password_hash("user123"),
            "role":                UserRole.user.value,
            "is_active":           True,
            "permission_overrides": [],
            "created_at":          now,
            "last_active":         None,
            "tenant_id":           "tenant_01",  # Regular user can access tenant_01
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
            "tenant_id":         "tenant_01",
            "camera_id":         "cam_1",
            "source_path":       "rtsp://LT_corridor:12345678@192.168.100.211/stream1",
            "target_fps":        5,
            "pipelines":         ["smoking_detection", "fight_detection", "fire_detection", "fall_detection", "weapon_tiling", "spiking", "ppe"],
            "enabled":           True,
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
        {},
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
    print("  m.hussain7006@gmail.com / superadmin123")
    print("  husain@lambdatheta.com / admin123")
    print("  ahsanshahid2010@hotmail.com       / ahsan123")
