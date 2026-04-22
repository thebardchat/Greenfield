"""
Tesseract OCR provider — local, zero-cloud, HIPAA-friendly.

Pipeline:
  PDF  → pdf2image (300 DPI, PIL Images)  → pytesseract → OcrResult
  Image → PIL.Image.open                  → pytesseract → OcrResult

Confidence is derived from pytesseract's word-level confidence data
(the `conf` column in image_to_data output). Words with conf == -1
(whitespace/layout tokens) are excluded from the mean.

Requires system packages:
  apt-get install tesseract-ocr poppler-utils
Python packages (in pyproject.toml):
  pytesseract, pdf2image, Pillow
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

try:
    import pytesseract
    from PIL import Image

    _TESSERACT_AVAILABLE = True
except ImportError:
    _TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError

    _PDF2IMAGE_AVAILABLE = True
except ImportError:
    _PDF2IMAGE_AVAILABLE = False

from .base import OcrProvider, OcrResult, OcrStatus

log = logging.getLogger(__name__)

# ─────────────────────────── Configuration ───────────────────────────
DPI = int(os.getenv("TESSERACT_DPI", "300"))
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "eng")
TESSERACT_CONFIG = os.getenv(
    "TESSERACT_CONFIG",
    "--oem 3 --psm 6 -c preserve_interword_spaces=1",
)
# Minimum acceptable word count before we flag the result as suspicious
MIN_WORD_COUNT = int(os.getenv("TESSERACT_MIN_WORDS", "10"))


class TesseractProvider(OcrProvider):
    """Local OCR via Tesseract + pdf2image."""

    name = "tesseract"

    # ─────────────────────────── Public API ──────────────────────────

    async def extract(self, file_path: Path, mime_type: str) -> OcrResult:
        """
        Run Tesseract on *file_path* and return an OcrResult.

        This method is async in signature to match the ABC, but the
        heavy work (pdf2image, pytesseract) is CPU-bound / blocking.
        Callers should run it in a thread executor if needed:
            loop.run_in_executor(None, provider.extract_sync, path, mime)
        """
        if not _TESSERACT_AVAILABLE:
            return OcrResult(
                text="",
                provider=self.name,
                status=OcrStatus.FAILED,
                error="pytesseract not installed — run: pip install pytesseract pillow",
            )

        start = self._start_timer()
        file_size = file_path.stat().st_size if file_path.exists() else 0

        try:
            if mime_type == "application/pdf":
                result = self._extract_pdf(file_path)
            else:
                result = self._extract_image(file_path)

            result.provider = self.name
            result.duration_seconds = self._elapsed(start)
            result.file_size_bytes = file_size
            result.mime_type = mime_type

            # Sanity check — suspiciously short output
            if result.succeeded and result.word_count < MIN_WORD_COUNT:
                log.warning(
                    "Tesseract returned only %d words for %s — may be image-heavy or scanned poorly",
                    result.word_count,
                    file_path.name,
                )

            return result

        except Exception as exc:  # noqa: BLE001
            log.exception("Tesseract extraction failed for %s", file_path)
            return OcrResult(
                text="",
                provider=self.name,
                status=OcrStatus.FAILED,
                error=str(exc),
                duration_seconds=self._elapsed(start),
                file_size_bytes=file_size,
                mime_type=mime_type,
            )

    # ─────────────────────────── PDF path ────────────────────────────

    def _extract_pdf(self, file_path: Path) -> OcrResult:
        if not _PDF2IMAGE_AVAILABLE:
            return OcrResult(
                text="",
                status=OcrStatus.FAILED,
                error="pdf2image not installed — run: pip install pdf2image",
            )

        try:
            images = convert_from_path(
                str(file_path),
                dpi=DPI,
                fmt="jpeg",          # JPEG is faster to decode than PNG for Tesseract
                thread_count=2,      # parallel page renders
                grayscale=True,      # faster; Tesseract handles BW better
            )
        except (PDFPageCountError, PDFSyntaxError) as exc:
            return OcrResult(
                text="",
                status=OcrStatus.FAILED,
                error=f"PDF could not be opened: {exc}",
            )

        return self._process_images(images)

    # ─────────────────────────── Image path ──────────────────────────

    def _extract_image(self, file_path: Path) -> OcrResult:
        try:
            img = Image.open(file_path)
            # Convert to grayscale for better Tesseract accuracy
            if img.mode not in ("L", "1"):
                img = img.convert("L")
            return self._process_images([img])
        except Exception as exc:  # noqa: BLE001
            return OcrResult(
                text="",
                status=OcrStatus.FAILED,
                error=f"Cannot open image: {exc}",
            )

    # ─────────────────────── Core processing ─────────────────────────

    def _process_images(self, images: list) -> OcrResult:
        """Run Tesseract on a list of PIL Images, one per page."""
        pages: list[str] = []
        page_confidences: list[float] = []

        for page_num, img in enumerate(images, start=1):
            try:
                text, conf = self._ocr_image(img)
                pages.append(text)
                page_confidences.append(conf)
                log.debug("Page %d: %d words, conf=%.3f", page_num, len(text.split()), conf)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to OCR page %d: %s", page_num, exc)
                pages.append("")
                page_confidences.append(0.0)

        full_text = "\n\n".join(p for p in pages if p.strip())
        mean_conf = (
            sum(page_confidences) / len(page_confidences) if page_confidences else 0.0
        )

        return OcrResult(
            text=full_text,
            page_count=len(images),
            pages=pages,
            confidence=mean_conf,
            page_confidences=page_confidences,
            status=OcrStatus.COMPLETED,
        )

    def _ocr_image(self, img: "Image.Image") -> tuple[str, float]:
        """
        OCR a single PIL Image.

        Returns (text, confidence) where confidence is 0.0–1.0.
        """
        # image_to_data gives per-word confidence scores (0-100 or -1)
        data = pytesseract.image_to_data(
            img,
            lang=TESSERACT_LANG,
            config=TESSERACT_CONFIG,
            output_type=pytesseract.Output.DICT,
        )

        # Filter to real words (conf != -1 means a recognized word token)
        confs = [c for c in data["conf"] if c != -1]
        mean_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.0

        # Get clean text (image_to_string is faster for the actual string)
        text = pytesseract.image_to_string(
            img,
            lang=TESSERACT_LANG,
            config=TESSERACT_CONFIG,
        ).strip()

        return text, mean_conf
