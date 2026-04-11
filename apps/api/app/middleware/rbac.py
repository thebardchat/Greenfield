"""Role-based access control middleware.

Uses the permission system from packages/shared/roles.py to
enforce access per endpoint. Checks JWT claims for user role
and organization_id, then validates against required permissions.
"""
