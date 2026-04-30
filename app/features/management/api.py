from datetime import datetime, timezone
from typing import List

from bson import ObjectId
from fastapi import Depends, HTTPException, status
from pymongo.database import Database

from app.core.custom_router import ProtectedSuperadminRouter
from app.db.session import get_db
from app.features.auth import schemas
from app.features.auth.api import get_user_by_email, serialize_user
from app.features.auth.models import PermissionEnum, UserRole
from app.features.auth.security import get_password_hash
from app.features.management.utils import get_effective_permissions

router = ProtectedSuperadminRouter()


# ──────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────

@router.get("/allUsers")
def list_users(db: Database = Depends(get_db)):
    """List all users with their effective permissions."""
    users = list(db.users.find())
    result = []
    for u in users:
        role_doc = db.roles.find_one({"name": u["role"]}) or {}
        u["_role_permissions"] = role_doc
        result.append({
            **serialize_user(u),
            "permissions": get_effective_permissions(u),
        })
    return result


@router.post(
    "/register",
    dependencies=[ProtectedSuperadminRouter.requires_permission(PermissionEnum.manage_users)],
)
def register_user(user_in: schemas.UserCreate, db: Database = Depends(get_db)):
    """Create a new user. Requires manage_users permission."""
    if get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    doc = {
        "email":               user_in.email,
        "full_name":           user_in.full_name,
        "hashed_password":     get_password_hash(user_in.password),
        "role":                user_in.role.value,
        "is_active":           True,
        "tenant_id":           user_in.tenant_id,
        "permission_overrides": [o.model_dump() for o in (user_in.overrides or [])],
        "created_at":          datetime.now(timezone.utc),
        "last_active":         None,
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id

    role_doc = db.roles.find_one({"name": doc["role"]}) or {}
    doc["_role_permissions"] = role_doc

    return {**serialize_user(doc), "permissions": get_effective_permissions(doc)}


@router.delete(
    "/deleteUser/{user_id}",
    dependencies=[ProtectedSuperadminRouter.requires_permission(PermissionEnum.manage_users)],
)
def delete_user(
    user_id: str,
    db: Database = Depends(get_db),
    current_user: dict = Depends(ProtectedSuperadminRouter.inject_current_user),
):
    """Delete a user. Cannot delete yourself."""
    if str(current_user["_id"]) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    result = db.users.delete_one({"_id": ObjectId(user_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    return {"detail": "User deleted successfully"}


@router.get("/user/{user_id}")
def get_user_by_id(user_id: str, db: Database = Depends(get_db)):
    """Fetch a single user by ID."""
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@router.patch("/changeRole/{user_id}")
def change_user_role(
    user_id: str,
    new_role: UserRole,
    db: Database = Depends(get_db),
    current_user: dict = Depends(ProtectedSuperadminRouter.inject_current_user),
):
    """Change a user's role. Cannot change your own role."""
    if str(current_user["_id"]) == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    result = db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": new_role.value}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    updated = db.users.find_one({"_id": ObjectId(user_id)})
    return serialize_user(updated)


@router.patch(
    "/updateUserPermissions/{user_id}",
    dependencies=[ProtectedSuperadminRouter.requires_permission(PermissionEnum.manage_permissions)],
)
def update_user_permissions(
    user_id: str,
    body: schemas.UserUpdatePermissions,
    db: Database = Depends(get_db),
):
    """
    Toggle permission overrides for a user.
    - If override already exists → remove it (revert to role default).
    - If override doesn't exist → add it.
    """
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = {
        o["permission_name"]: o
        for o in user.get("permission_overrides", [])
    }

    for change in body.changes:
        pname = change.permission_name.value
        if pname in existing:
            # Override exists → remove (revert to role default)
            del existing[pname]
        else:
            # No override → create new one
            existing[pname] = {"permission_name": pname, "value": change.value}

    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"permission_overrides": list(existing.values())}},
    )

    updated = db.users.find_one({"_id": ObjectId(user_id)})
    role_doc = db.roles.find_one({"name": updated["role"]}) or {}
    updated["_role_permissions"] = role_doc

    return {**serialize_user(updated), "permissions": get_effective_permissions(updated)}


# ──────────────────────────────────────────────
# Roles
# ──────────────────────────────────────────────

@router.get("/roles")
def get_roles(db: Database = Depends(get_db)):
    """Get all roles with their default permissions."""
    roles = list(db.roles.find({}, {"_id": 0}))
    return roles


@router.get("/roleCounts")
def role_counts(db: Database = Depends(get_db)):
    """Get how many users each role has."""
    pipeline = [{"$group": {"_id": "$role", "count": {"$sum": 1}}}]
    return [{"role": r["_id"], "count": r["count"]} for r in db.users.aggregate(pipeline)]
