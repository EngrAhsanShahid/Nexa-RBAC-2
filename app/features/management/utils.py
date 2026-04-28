from app.features.auth.models import PermissionEnum


def has_permission(user: dict, permission: PermissionEnum) -> bool:
    """
    2-layer RBAC check — mirrors the PostgreSQL project's logic:
      1. User-specific override  (stored in user["permission_overrides"])
      2. Fallback → role default (pre-loaded in user["_role_permissions"])
    """
    # Layer 1: personal overrides
    for override in user.get("permission_overrides", []):
        if override.get("permission_name") == permission.value:
            return override.get("value", False)

    # Layer 2: role default
    role = user.get("_role_permissions", {})
    return bool(role.get(permission.value, False))


def get_effective_permissions(user: dict) -> dict:
    """
    Returns the final permission map for a user (role defaults + overrides applied).
    Requires user["_role_permissions"] to be pre-loaded (done by get_current_user).
    """
    role = user.get("_role_permissions", {})

    # Start from role defaults
    permissions = {perm.value: bool(role.get(perm.value, False)) for perm in PermissionEnum}

    # Apply user-specific overrides
    for override in user.get("permission_overrides", []):
        pname = override.get("permission_name")
        if pname in permissions:
            permissions[pname] = override.get("value", False)

    return permissions
