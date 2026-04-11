"""HIPAA audit middleware.

Intercepts every request and writes to the audit_log table.
Captures: user_id, org_id, action, resource, IP, user-agent, session.
Logs both reads and writes of PHI-containing resources.
"""
