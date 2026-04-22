"""
Base classes for OCR providers.

All OCR providers implement OcrProvider and return OcrResult.
The pipeline selects providers by confidence: Tesseract first,
cloud fallback (Google Document AI or AWS Textract) if confidence
is below the configured threshold.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class OcrStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    LOW_CONFIDENCE = "low_confidence"  # completed but below threshold


@dataclass
class OcrResult:
    """Structured output from any OCR provider."""

    # Core text
    text: str                          # full extracted text, pages joined with \n\n
    page_count: int = 0
    pages: list[str] = field(default_factory=list)  # per-page text

    # Quality
    confidence: float = 0.0           # 0.0–1.0; mean across all pages
    page_confidences: list[float] = field(default_factory=list)

    # Metadata
    provider: str = "unknown"         # "tesseract" | "document_ai" | "textract"
    duration_seconds: float = 0.0
    file_size_bytes: int = 0
    mime_type: str = ""

    # Structured extraction (populated by CruncherClient.parse_eob later)
    structured: Optional[dict] = None

    # Error info (set when provider fails)
    error: Optional[str] = None
    status: OcrStatus = OcrStatus.COMPLETED

    @property
    def succeeded(self) -> bool:
        return self.status in (OcrStatus.COMPLETED, OcrStatus.LOW_CONFIDENCE)

    @property
    def word_count(self) -> int:
        return len(self.text.split()) if self.text else 0

    def summary(self) -> dict:
        """Compact dict for logging / status storage."""
        return {
            "provider": self.provider,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "confidence": round(self.confidence, 3),
            "duration_seconds": round(self.duration_seconds, 2),
            "status": self.status.value,
            "error": self.error,
        }


class OcrProvider(ABC):
    """Abstract base for OCR backends."""

    name: str = "base"

    @abstractmethod
    async def extract(self, file_path: Path, mime_type: str) -> OcrResult:
        """
        Extract text from *file_path*.

        Args:
            file_path: Absolute path to the file on disk.
            mime_type: MIME type of the file (e.g. "application/pdf").

        Returns:
            OcrResult with text, confidence, and metadata populated.
        """
        ...

    def _start_timer(self) -> float:
        return time.perf_counter()

    def _elapsed(self, start: float) -> float:
        return round(time.perf_counter() - start, 3)
