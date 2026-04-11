"""HIPAA audit middleware.

Intercepts every request and writes to the audit_log table.
Captures: user_id, org_id, action, resource, IP, user-agent, session.
Logs both reads and writes of PHI-containing resources.
Fire-and-forget via asyncio.create_task so it never slows responses.
"""

import asyncio
import logging
from typing import Callable

from fastapi import Request, Response
from jose import JWTError, jwt
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.dependencies import engine
from app.services.auth import ALGORITHM

logger = logging.getLogger(__name__)

SKIP_PATHS = {"/health", "/docs", "/openapi.json"}

METHOD_ACTION_MAP = {
    "POST": "create",
    "GET": "read",
    "PATCH": "update",
    "PUT": "update",
    "DELETE": "delete",
}


def _extract_resource_type(path: str) -> str | None:
    """Extract resource type from API path (e.g., /api/claims/... -> claim)."""
    parts = path.strip("/").split("/")
    # Expect paths like /api/<resource>/...
    if len(parts) >= 2 and parts[0] == "api":
        # Singularize: "claims" -> "claim", "facilities" -> "facility"
        resource = parts[1]
        if resource.endswith("ies"):
            return resource[:-3] + "y"
        if resource.endswith("s"):
            return resource[:-1]
        return resource
    return None


def _extract_jwt_claims(request: Request) -> dict:
    """Try to extract user_id, org_id, session_id from Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return {}
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
        return {
            "user_id": payload.get("sub"),
            "org_id": payload.get("org_id"),
            "session_id": payload.get("jti"),
        }
    except JWTError:
        return {}


async def _write_audit_log(
    user_id: str | None,
    org_id: str | None,
    ip_address: str | None,
    user_agent: str | None,
    action: str,
    resource_type: str | None,
    session_id: str | None,
) -> None:
    """Insert a row into audit_log using a raw async connection."""
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO audit_log "
                    "(user_id, organization_id, session_id, ip_address, user_agent, "
                    "action, resource_type) "
                    "VALUES (:user_id, :org_id, :session_id, :ip_address, :user_agent, "
                    ":action, :resource_type)"
                ),
                {
                    "user_id": user_id,
                    "org_id": org_id,
                    "session_id": session_id,
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "action": action,
                    "resource_type": resource_type,
                },
            )
    except Exception:
        logger.exception("Failed to write audit log entry")


class AuditMiddleware(BaseHTTPMiddleware):
    """HIPAA-compliant audit logging middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-auditable paths
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        response = await call_next(request)

        # Build audit record after response
        method = request.method.upper()
        action_verb = METHOD_ACTION_MAP.get(method, method.lower())
        resource_type = _extract_resource_type(request.url.path)
        action = f"{resource_type}.{action_verb}" if resource_type else action_verb

        claims = _extract_jwt_claims(request)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        # Fire-and-forget: don't block the response
        asyncio.create_task(
            _write_audit_log(
                user_id=claims.get("user_id"),
                org_id=claims.get("org_id"),
                ip_address=ip_address,
                user_agent=user_agent,
                action=action,
                resource_type=resource_type,
                session_id=claims.get("session_id"),
            )
        )

        return response
