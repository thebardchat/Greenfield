from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    BILLER = "biller"
    CODER = "coder"
    CLIENT = "client"
    AUDITOR = "auditor"


class AssignmentRole(StrEnum):
    BILLER = "biller"
    CODER = "coder"
    LEAD = "lead"
    BACKUP = "backup"


# Which user roles can access which features
ROLE_PERMISSIONS: dict[UserRole, set[str]] = {
    UserRole.SUPER_ADMIN: {"*"},
    UserRole.ORG_ADMIN: {
        "claims:read", "claims:write", "claims:assign",
        "patients:read", "patients:write",
        "facilities:read", "facilities:write",
        "assignments:read", "assignments:write",
        "tickets:read", "tickets:write", "tickets:assign",
        "credentials:read", "credentials:write",
        "documents:read", "documents:upload",
        "reports:read",
        "users:read", "users:write",
        "cruncher:chat",
    },
    UserRole.BILLER: {
        "claims:read", "claims:write",
        "patients:read",
        "facilities:read",
        "tickets:read", "tickets:write",
        "credentials:read",
        "documents:read", "documents:upload",
        "reports:read",
        "cruncher:chat",
    },
    UserRole.CODER: {
        "claims:read", "claims:write",
        "patients:read",
        "facilities:read",
        "tickets:read", "tickets:write",
        "credentials:read",
        "documents:read",
        "cruncher:chat",
    },
    UserRole.CLIENT: {
        "claims:read",
        "documents:read", "documents:upload",
        "tickets:read", "tickets:write",
        "reports:read",
    },
    UserRole.AUDITOR: {
        "claims:read",
        "patients:read",
        "documents:read",
        "tickets:read",
        "credentials:read",
        "reports:read",
    },
}


def has_permission(role: UserRole, permission: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return "*" in perms or permission in perms
