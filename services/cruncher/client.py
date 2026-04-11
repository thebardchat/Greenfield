"""Cruncher AI — Claude API integration for claim intelligence.

Capabilities:
- Interactive Q&A for billers/coders (CPT/ICD lookup, coding guidance)
- Auto-flagging of OCR results (missing fields, inconsistencies)
- Denial analysis and appeal strategy
- RAG over claim history via pgvector

PHI handling: De-identify patient data before sending to Claude API
unless an Anthropic BAA is in place.
"""


class CruncherClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def chat(self, message: str, context: dict | None = None) -> str:
        """Interactive coder/biller assistant chat."""
        ...

    async def auto_flag(self, ocr_text: str, structured_data: dict) -> list[dict]:
        """Scan OCR results for issues. Returns list of flags."""
        ...

    async def analyze_denial(self, claim_data: dict, denial_reason: str) -> dict:
        """Analyze denial and suggest appeal strategy."""
        ...
