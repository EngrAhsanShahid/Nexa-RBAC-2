from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from app.db.session import get_db
from app.features.auth import models
from app.features.auth.api import get_current_user, require_role
from app.features.management.utils import has_permission


class ProtectedRouter(APIRouter):
    """
    Router that requires a valid JWT for every endpoint.
    Use this for features accessible to any logged-in user (all roles).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Auto-attach token validation to every endpoint registered on this router
        self.dependencies.append(Depends(self._current_user_dependency))

    @staticmethod
    def _current_user_dependency(
        current_user: dict = Depends(get_current_user),
    ) -> dict:
        return current_user

    @staticmethod
    def inject_current_user(
        current_user: dict = Depends(_current_user_dependency),
    ) -> dict:
        """
        Usage — get user inside endpoint body:
            def endpoint(current_user = Depends(ProtectedRouter.inject_current_user))
        """
        return current_user

    @staticmethod
    def requires_permission(permission: models.PermissionEnum):
        """
        Usage 1 — guard only (no user object needed in endpoint):
            @router.get("/", dependencies=[ProtectedRouter.requires_permission(PermissionEnum.view_stream)])

        Usage 2 — guard + get current user:
            def endpoint(current_user = ProtectedRouter.requires_permission(PermissionEnum.view_stream))
        """

        def dependency(
            db: Database = Depends(get_db),
            current_user: dict = Depends(ProtectedRouter._current_user_dependency),
        ) -> dict:
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )
            return current_user

        return Depends(dependency)


class ProtectedSuperadminRouter(APIRouter):
    """
    Router that requires the Superadmin role for every endpoint.
    Use this for user/role management operations.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dependencies.append(Depends(self._current_user_dependency))

    @staticmethod
    def _current_user_dependency(
        current_user: dict = Depends(require_role(models.UserRole.superadmin)),
    ) -> dict:
        return current_user

    @staticmethod
    def inject_current_user(
        current_user: dict = Depends(_current_user_dependency),
    ) -> dict:
        """
        Usage:
            def endpoint(current_user = Depends(ProtectedSuperadminRouter.inject_current_user))
        """
        return current_user

    @staticmethod
    def requires_permission(permission: models.PermissionEnum):
        """
        Same as ProtectedRouter.requires_permission but also enforces Superadmin role first.

        Usage:
            dependencies=[ProtectedSuperadminRouter.requires_permission(PermissionEnum.manage_users)]
        """

        def dependency(
            db: Database = Depends(get_db),
            current_user: dict = Depends(ProtectedSuperadminRouter._current_user_dependency),
        ) -> dict:
            if not has_permission(current_user, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {permission.value}",
                )
            return current_user

        return Depends(dependency)
