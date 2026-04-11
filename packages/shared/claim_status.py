from enum import StrEnum


class ClaimStatus(StrEnum):
    SUBMITTED = "submitted"
    OCR_PROCESSING = "ocr_processing"
    OCR_FAILED = "ocr_failed"
    READY_FOR_REVIEW = "ready_for_review"
    IN_PROGRESS = "in_progress"
    CODED = "coded"
    BILLED = "billed"
    PAID = "paid"
    DENIED = "denied"
    APPEALED = "appealed"
    VOID = "void"


# Valid status transitions (from -> set of allowed destinations)
VALID_TRANSITIONS: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.SUBMITTED: {ClaimStatus.OCR_PROCESSING},
    ClaimStatus.OCR_PROCESSING: {ClaimStatus.READY_FOR_REVIEW, ClaimStatus.OCR_FAILED},
    ClaimStatus.OCR_FAILED: {ClaimStatus.OCR_PROCESSING, ClaimStatus.READY_FOR_REVIEW},
    ClaimStatus.READY_FOR_REVIEW: {ClaimStatus.IN_PROGRESS, ClaimStatus.VOID},
    ClaimStatus.IN_PROGRESS: {ClaimStatus.CODED, ClaimStatus.READY_FOR_REVIEW, ClaimStatus.VOID},
    ClaimStatus.CODED: {ClaimStatus.BILLED, ClaimStatus.IN_PROGRESS, ClaimStatus.VOID},
    ClaimStatus.BILLED: {ClaimStatus.PAID, ClaimStatus.DENIED, ClaimStatus.VOID},
    ClaimStatus.PAID: set(),
    ClaimStatus.DENIED: {ClaimStatus.APPEALED, ClaimStatus.VOID},
    ClaimStatus.APPEALED: {ClaimStatus.BILLED, ClaimStatus.DENIED, ClaimStatus.VOID},
    ClaimStatus.VOID: set(),
}


def can_transition(current: ClaimStatus, target: ClaimStatus) -> bool:
    return target in VALID_TRANSITIONS.get(current, set())
