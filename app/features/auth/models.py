from enum import Enum


class UserRole(str, Enum):
    superadmin = "Superadmin"
    admin      = "Admin"
    user       = "User"


class PermissionEnum(str, Enum):
    add_camera          = "add_camera"
    delete_camera       = "delete_camera"
    view_stream         = "view_stream"
    add_tenant          = "add_tenant"
    delete_tenant       = "delete_tenant"
    manage_users        = "manage_users"
    manage_permissions  = "manage_permissions"
