"""BAA (Business Associate Agreement) safety gate.

HIPAA requires a signed BAA with any external vendor that processes PHI on your behalf.
Before sending patient or claim data to the Claude/Anthropic API, a BAA must be in place.

If BAA_SIGNED is false in config, all Cruncher routes that could transmit PHI return 403.
"""

from fastapi import HTTPException, status

from app.config import settings


def require_baa() -> None:
    """Raise 403 if no BAA is on file with Anthropic.

    Call this at the top of any route that sends claim or patient data to the Claude API.
    """
    if not settings.baa_signed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "BAA required before sending patient data to external AI. "
                "A signed Business Associate Agreement with Anthropic must be on file. "
                "Set BAA_SIGNED=true in your environment once the agreement is executed. "
                "Contact your compliance officer or admin."
            ),
        )
