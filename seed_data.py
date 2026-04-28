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


if __name__ == "__main__":
    seed_roles()
    seed_users()
    print("✅ All data seeded successfully!")
    print()
    print("Login credentials:")
    print("  superadmin@example.com / superadmin123")
    print("  admin@example.com      / admin123")
    print("  user@example.com       / user123")
