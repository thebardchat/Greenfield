"""Claude tool definitions for Claim Cruncher.

These tools are passed to the Claude API so the AI can query claim data,
flag issues, create tickets, and look up billing codes — all grounded in
real data from the database rather than hallucinated.

Tool execution happens in the router layer (cruncher.py), which has DB
access. The definitions here are pure schemas + metadata.
"""

from typing import Any

# ---------------------------------------------------------------------------
# Tool schemas (passed to Claude API as tools=[...])
# ---------------------------------------------------------------------------

CRUNCHER_TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_claim",
        "description": (
            "Retrieve full claim details from the database including dates of service, "
            "charges, NPI numbers, status, flags, and assignment info. "
            "Use this before analyzing any claim."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "UUID of the claim to retrieve",
                }
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "get_claim_lines",
        "description": (
            "Get the individual service line items for a claim — CPT codes, "
            "diagnosis codes (ICD-10), units, charges, and modifiers. "
            "Use this to review coding accuracy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "UUID of the claim",
                }
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "get_patient_claim_history",
        "description": (
            "Retrieve prior claims for a patient to check for duplicate submissions, "
            "continuity of care, and prior authorization patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "UUID of the patient",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of prior claims to retrieve (default 10)",
                    "default": 10,
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_claim_documents",
        "description": (
            "List documents attached to a claim — EOBs, clinical notes, authorizations. "
            "Returns file names, OCR status, and OCR text if available."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "UUID of the claim",
                }
            },
            "required": ["claim_id"],
        },
    },
    {
        "name": "flag_claim",
        "description": (
            "Mark a claim as flagged with a specific reason. Use this when you detect "
            "a billing error, missing information, duplicate, or compliance issue. "
            "Always explain the flag reason clearly — billers will read it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "UUID of the claim to flag",
                },
                "reason": {
                    "type": "string",
                    "description": "Clear, actionable explanation of the issue (1-3 sentences)",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority level 1-5 (1=low, 3=medium, 5=critical). Default 2.",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2,
                },
            },
            "required": ["claim_id", "reason"],
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "Create a work ticket for a claim that needs human review or action. "
            "Use for issues that can't be auto-resolved — missing auth, payer dispute, "
            "coding question, or denial appeal work."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "claim_id": {
                    "type": "string",
                    "description": "UUID of the claim this ticket relates to",
                },
                "title": {
                    "type": "string",
                    "description": "Short title for the ticket (under 80 chars)",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of what needs to be done",
                },
                "ticket_type": {
                    "type": "string",
                    "enum": [
                        "coding_review",
                        "billing_review",
                        "missing_info",
                        "denial_appeal",
                        "credential_issue",
                        "general",
                    ],
                    "description": "Category of work required",
                },
                "priority": {
                    "type": "integer",
                    "description": "Priority 1-5 (default 2)",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 2,
                },
            },
            "required": ["claim_id", "title", "description", "ticket_type"],
        },
    },
    {
        "name": "search_similar_claims",
        "description": (
            "Search for similar claims by procedure codes, diagnosis codes, or denial reasons "
            "to find precedents, patterns, or prior successful appeals. "
            "Uses semantic search over the claim history."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for (e.g. 'lumbar fusion with modifier 62', 'medical necessity denial')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of similar claims to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
]

# ---------------------------------------------------------------------------
# Flagging-only tool set (used by auto_flag — faster, cheaper)
# ---------------------------------------------------------------------------

AUTO_FLAG_TOOLS: list[dict[str, Any]] = [
    t for t in CRUNCHER_TOOLS if t["name"] in {"flag_claim", "create_ticket"}
]

# ---------------------------------------------------------------------------
# Tool name registry for dispatch
# ---------------------------------------------------------------------------

TOOL_NAMES = {t["name"] for t in CRUNCHER_TOOLS}

# ---------------------------------------------------------------------------
# Common flag patterns (fed as examples into auto_flag prompts)
# ---------------------------------------------------------------------------

FLAG_RULES = [
    "Missing or invalid NPI (must be 10 digits)",
    "Date of service after today or before patient DOB",
    "Total charges of $0.00 or negative",
    "Duplicate claim number already in system",
    "CPT code and place of service mismatch (e.g. inpatient code billed as 11/office)",
    "Modifier missing for bilateral procedure or team surgery",
    "ICD-10 code not valid for stated date of service",
    "Provider NPI not credentialed at this facility",
    "Missing referring NPI when required by payer",
    "Date of service gap > 1 day for inpatient stay with no weekend/holiday explanation",
]
