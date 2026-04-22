"""CruncherClient — Claude AI integration for Claim Cruncher.

Three modes:
  1. chat()        — Streaming interactive assistant for billers/coders.
                     Uses claude-sonnet-4-6, full tool use, SSE streaming.
  2. auto_flag()   — Fast batch scan of OCR results for claim issues.
                     Uses claude-haiku (cheap + fast), returns structured flags.
  3. analyze_denial() — Full denial analysis + appeal strategy generation.
                     Uses claude-sonnet-4-6, returns structured dict.
  4. parse_eob()   — Extract structured fields from OCR'd EOB text.
                     Returns normalized dict ready for DB write.

PHI handling:
  De-identify patient data before sending to the API unless an Anthropic
  BAA is in place. See `deidentify()` below — swap in your actual de-id
  logic or set ANTHROPIC_BAA=true in .env to bypass.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from .tools import CRUNCHER_TOOLS, AUTO_FLAG_TOOLS, FLAG_RULES

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_CHAT = """\
You are Cruncher, an AI assistant embedded in Claim Cruncher — a medical billing platform
used by professional billers and coders. You help them process claims accurately and efficiently.

## Your capabilities
- Answer questions about CPT codes, ICD-10 codes, modifiers, and CMS billing guidelines
- Review claim data for errors: missing NPI, date inconsistencies, duplicate submissions,
  mismatched place-of-service codes, missing modifiers for bilateral procedures
- Analyze claim denials and recommend appeal strategies with specific payer logic
- Search similar claims to find precedents and prior successful appeals
- Flag claims and create tickets for issues that need human review

## Rules
- Always cite specific CPT/ICD codes by number when discussing them
- Flag uncertainty — say "verify with the payer" when guidelines are ambiguous
- Never fabricate codes or invent claim data. If unsure, say so
- Respect the user's expertise — they are trained billers and coders
- Keep responses concise and actionable; billers are busy
- When you use a tool, explain to the user what you're doing and why
- For HIPAA: do not repeat patient names or SSNs back verbatim in your response

## Tool use
You have access to live claim data. Always retrieve claim details before analyzing a claim.
When you detect an issue, use flag_claim and/or create_ticket immediately — don't just
mention the issue in chat and hope the user catches it.
"""

_SYSTEM_AUTO_FLAG = """\
You are a medical billing compliance scanner. You will be given OCR text and structured
data extracted from a claim document. Your job is to identify billing errors, compliance
issues, and missing fields.

For each issue you find, call flag_claim or create_ticket immediately.

Known error patterns to check:
{rules}

Be thorough but precise. Do not flag things that aren't actual issues. Each flag should
be a specific, actionable finding — not a vague concern.
""".format(rules="\n".join(f"- {r}" for r in FLAG_RULES))

_SYSTEM_DENIAL = """\
You are a medical billing denial analyst. You will be given claim data and a denial reason.
Your job is to:
1. Identify the root cause of the denial (coding error, authorization missing, timely filing, etc.)
2. Determine if the denial is disputable
3. Provide a specific appeal strategy with exact steps
4. Draft key language for the appeal letter

Be specific — cite exact payer rules, CMS guidelines, or CPT/ICD documentation when available.
Return a structured analysis.
"""

_SYSTEM_EOB = """\
You are a medical billing data extraction expert. Extract structured fields from the
Explanation of Benefits (EOB) text provided. Return a JSON object with these fields
(use null for any field not found in the document):

{
  "claim_number": string | null,
  "patient_name": string | null,
  "patient_id": string | null,
  "date_of_service_from": "YYYY-MM-DD" | null,
  "date_of_service_to": "YYYY-MM-DD" | null,
  "provider_name": string | null,
  "provider_npi": string | null,
  "total_charges": number | null,
  "total_paid": number | null,
  "patient_responsibility": number | null,
  "denial_reason": string | null,
  "remark_codes": [string],
  "adjustment_codes": [string],
  "service_lines": [
    {
      "cpt_code": string,
      "description": string | null,
      "units": number | null,
      "charge": number | null,
      "paid": number | null,
      "denial_reason": string | null
    }
  ]
}

Return ONLY the JSON object, no prose.
"""

# ---------------------------------------------------------------------------
# De-identification (PHI guard)
# ---------------------------------------------------------------------------

_PHI_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),          # SSN
    (re.compile(r"\b\d{3}-\d{3}-\d{4}\b"), "[PHONE]"),        # Phone
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[EMAIL]"),
]


def deidentify(text: str, baa_in_place: bool = False) -> str:
    """Strip obvious PHI from text before sending to Claude API.

    If a BAA is in place (ANTHROPIC_BAA=true in env), pass through unmodified.
    This is a best-effort regex approach — production systems should use a
    dedicated de-identification service (AWS Comprehend Medical, etc).
    """
    if baa_in_place:
        return text
    for pattern, replacement in _PHI_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


# ---------------------------------------------------------------------------
# CruncherClient
# ---------------------------------------------------------------------------


class CruncherClient:
    """Async Claude client for Claim Cruncher AI features."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        flag_model: str = "claude-haiku-4-5-20251001",
        baa_in_place: bool = False,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.flag_model = flag_model
        self.baa_in_place = baa_in_place

    # -----------------------------------------------------------------------
    # 1. Interactive streaming chat
    # -----------------------------------------------------------------------

    async def chat_stream(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        tool_executor: "ToolExecutor | None" = None,
        max_iterations: int = 10,
    ) -> AsyncIterator[str]:
        """Streaming chat with agentic tool use.

        Yields SSE-compatible text chunks. Tool calls are executed via
        `tool_executor` (provided by the router, has DB access).

        Usage in router:
            async for chunk in client.chat_stream(message, tool_executor=executor):
                yield f"data: {chunk}\\n\\n"
        """
        messages: list[dict] = []
        if context:
            ctx_text = json.dumps(context, default=str, indent=2)
            messages.append({
                "role": "user",
                "content": f"<context>\n{ctx_text}\n</context>\n\n{message}",
            })
        else:
            messages.append({"role": "user", "content": message})

        for _ in range(max_iterations):
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=4096,
                system=_SYSTEM_CHAT,
                tools=CRUNCHER_TOOLS,
                messages=messages,
            ) as stream:
                tool_uses: list[dict] = []
                assistant_text = ""

                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                assistant_text += delta.text
                                yield delta.text
                            elif hasattr(delta, "partial_json"):
                                # Tool input streaming — buffer, don't yield
                                pass
                        elif event.type == "content_block_stop":
                            pass

                final = await stream.get_final_message()

            # Build assistant turn for conversation history
            messages.append({"role": "assistant", "content": final.content})

            # Check stop reason
            if final.stop_reason != "tool_use":
                break

            # Execute tool calls
            tool_results = []
            for block in final.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block, tool_executor)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

    # -----------------------------------------------------------------------
    # 2. Auto-flag (fast, Haiku model)
    # -----------------------------------------------------------------------

    async def auto_flag(
        self,
        claim_id: str,
        ocr_text: str,
        structured_data: dict[str, Any],
        tool_executor: "ToolExecutor | None" = None,
    ) -> list[dict[str, Any]]:
        """Scan OCR results and structured claim data for billing issues.

        Returns a list of flag dicts:
          [{"reason": str, "priority": int, "ticket_created": bool}, ...]
        """
        safe_text = deidentify(ocr_text, self.baa_in_place)
        safe_data = json.dumps(structured_data, default=str, indent=2)

        user_content = (
            f"Claim ID: {claim_id}\n\n"
            f"OCR TEXT:\n{safe_text}\n\n"
            f"STRUCTURED DATA:\n{safe_data}\n\n"
            "Scan for billing errors and compliance issues. "
            "Use flag_claim and create_ticket for every issue you find."
        )

        messages = [{"role": "user", "content": user_content}]
        flags: list[dict[str, Any]] = []

        for _ in range(5):  # max 5 tool-call rounds
            response = await self._client.messages.create(
                model=self.flag_model,
                max_tokens=2048,
                system=_SYSTEM_AUTO_FLAG,
                tools=AUTO_FLAG_TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await self._execute_tool(block, tool_executor)
                    if block.name == "flag_claim":
                        flags.append({
                            "reason": block.input.get("reason", ""),
                            "priority": block.input.get("priority", 2),
                            "ticket_created": False,
                        })
                    elif block.name == "create_ticket":
                        flags.append({
                            "reason": block.input.get("description", ""),
                            "priority": block.input.get("priority", 2),
                            "ticket_created": True,
                        })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return flags

    # -----------------------------------------------------------------------
    # 3. Denial analysis
    # -----------------------------------------------------------------------

    async def analyze_denial(
        self,
        claim_data: dict[str, Any],
        denial_reason: str,
        claim_lines: list[dict] | None = None,
        similar_claims: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Analyze a denial and return structured appeal strategy.

        Returns:
          {
            "root_cause": str,
            "disputable": bool,
            "dispute_likelihood": "high" | "medium" | "low",
            "appeal_strategy": str,
            "appeal_steps": [str, ...],
            "appeal_letter_language": str,
            "documentation_needed": [str, ...],
            "timely_filing_deadline": str | None,
          }
        """
        safe_data = deidentify(json.dumps(claim_data, default=str, indent=2), self.baa_in_place)
        parts = [
            f"CLAIM DATA:\n{safe_data}",
            f"DENIAL REASON: {denial_reason}",
        ]
        if claim_lines:
            parts.append(f"SERVICE LINES:\n{json.dumps(claim_lines, default=str, indent=2)}")
        if similar_claims:
            parts.append(
                f"SIMILAR PRIOR CLAIMS (for context):\n"
                f"{json.dumps(similar_claims, default=str, indent=2)}"
            )

        parts.append(
            "\nProvide a complete denial analysis. Return a JSON object with these exact keys: "
            "root_cause, disputable, dispute_likelihood, appeal_strategy, appeal_steps, "
            "appeal_letter_language, documentation_needed, timely_filing_deadline."
        )

        response = await self._client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=_SYSTEM_DENIAL,
            messages=[{"role": "user", "content": "\n\n".join(parts)}],
        )

        raw = response.content[0].text if response.content else "{}"
        # Extract JSON from response (Claude may add prose before/after)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {
            "root_cause": denial_reason,
            "disputable": None,
            "dispute_likelihood": "unknown",
            "appeal_strategy": raw,
            "appeal_steps": [],
            "appeal_letter_language": "",
            "documentation_needed": [],
            "timely_filing_deadline": None,
        }

    # -----------------------------------------------------------------------
    # 4. EOB parsing
    # -----------------------------------------------------------------------

    async def parse_eob(self, ocr_text: str) -> dict[str, Any]:
        """Extract structured fields from OCR'd EOB text.

        Returns a normalized dict ready for writing to claim_documents.ocr_structured.
        """
        safe_text = deidentify(ocr_text, self.baa_in_place)

        response = await self._client.messages.create(
            model=self.flag_model,  # Haiku is fine for extraction
            max_tokens=2048,
            system=_SYSTEM_EOB,
            messages=[{"role": "user", "content": f"Extract fields from this EOB:\n\n{safe_text}"}],
        )

        raw = response.content[0].text if response.content else "{}"
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {"raw_text": raw, "parse_error": True}

    # -----------------------------------------------------------------------
    # Internal tool dispatcher
    # -----------------------------------------------------------------------

    async def _execute_tool(
        self, block: Any, executor: "ToolExecutor | None"
    ) -> dict[str, Any]:
        """Dispatch a Claude tool_use block to the executor."""
        if executor is None:
            return {"error": "No tool executor available", "tool": block.name}
        try:
            return await executor.execute(block.name, block.input)
        except Exception as e:
            return {"error": str(e), "tool": block.name}


# ---------------------------------------------------------------------------
# ToolExecutor protocol (implemented in the router layer)
# ---------------------------------------------------------------------------


class ToolExecutor:
    """Base class for tool execution. Subclass in the router with DB access."""

    async def execute(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
