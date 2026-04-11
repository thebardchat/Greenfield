"""Role-based access control middleware.

Uses the permission system from packages/shared/roles.py to
enforce access per endpoint. Checks JWT claims for user role
and organization_id, then validates against required permissions.
"""

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models.user import User
from app.services.auth import decode_token

# Import from shared package — installed via pip install -e packages/shared
# or available on sys.path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "packages"))
from shared.roles import UserRole, has_permission


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the Authorization header.

    Returns the User ORM object. Raises 401 if token is missing, invalid,
    or the user is inactive/deleted.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header[7:]
    payload = decode_token(token)

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload["sub"]

    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(user_id),
            User.is_active.is_(True),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_permission(permission: str) -> Callable:
    """Return a FastAPI dependency that checks the user has the given permission.

    Usage:
        @router.get("/claims/", dependencies=[Depends(require_permission("claims:read"))])
    """

    async def _check_permission(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if not has_permission(UserRole(current_user.role), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}",
            )
        return current_user

    return _check_permission


def require_org_access(org_id_param: str = "org_id") -> Callable:
    """Return a FastAPI dependency that ensures the user belongs to the requested org.

    Super admins bypass this check. For all other roles, the user's organization_id
    must match the org_id path/query parameter.

    Usage:
        @router.get("/organizations/{org_id}/claims/",
                     dependencies=[Depends(require_org_access("org_id"))])
    """

    async def _check_org_access(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> User:
        # Super admins can access any org
        if current_user.role == UserRole.SUPER_ADMIN:
            return current_user

        # Get org_id from path params, query params, or body
        requested_org_id = request.path_params.get(org_id_param)
        if requested_org_id is None:
            requested_org_id = request.query_params.get(org_id_param)

        if requested_org_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required parameter: {org_id_param}",
            )

        if str(current_user.organization_id) != str(requested_org_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: organization mismatch",
            )

        return current_user

    return _check_org_access
