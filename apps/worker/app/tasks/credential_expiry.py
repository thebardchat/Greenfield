"""Credential expiry checker — runs daily via cron.

Scans credentials table for upcoming expirations and creates
credential_alerts records + notifications.
"""


async def check_credential_expiry(ctx):
    """Check for credentials expiring in 30/60/90 days."""
    ...
