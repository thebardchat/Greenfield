"""Synthetic OCR pipeline test — fake claim data, no real PHI.

Generates a test PDF with fake CMS-1500-style data and runs it
through TesseractProvider to verify the pipeline produces output.

Run: python tests/test_ocr_pipeline.py
Requires: fpdf2, pytesseract, pdf2image, poppler-utils, tesseract-ocr
"""

import asyncio
import os
import sys
import tempfile

# Make sure we can import from the worker package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "worker"))


FAKE_CLAIM = {
    "patient_name": "DOE, JANE",
    "date_of_birth": "01/15/1985",
    "patient_id": "MRN-TEST-00001",
    "insurance_id": "INS-FAKE-99999",
    "provider_npi": "1234567890",
    "date_of_service": "04/01/2026",
    "diagnosis_code": "M54.5",
    "cpt_code": "99213",
    "total_charge": "$150.00",
    "place_of_service": "11",
    "claim_number": "CLM-2026-SYNTHETIC-001",
}


def generate_test_pdf(path: str) -> None:
    """Generate a simple test PDF with fake CMS-1500-style content."""
    from fpdf import FPDF  # type: ignore

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)

    pdf.cell(0, 10, "CMS-1500 HEALTH INSURANCE CLAIM FORM - SYNTHETIC TEST", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "-" * 60, new_x="LMARGIN", new_y="NEXT")

    for key, value in FAKE_CLAIM.items():
        label = key.replace("_", " ").upper()
        pdf.cell(80, 8, f"{label}:", border=0)
        pdf.cell(0, 8, value, new_x="LMARGIN", new_y="NEXT")

    pdf.cell(0, 8, "-" * 60, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "*** SYNTHETIC TEST DATA - NOT A REAL CLAIM ***", new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)


def generate_test_image(path: str) -> None:
    """Fallback: generate a PNG image with fake claim text using Pillow."""
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    img = Image.new("RGB", (800, 600), color="white")
    draw = ImageDraw.Draw(img)

    y = 20
    draw.text((20, y), "CMS-1500 SYNTHETIC TEST", fill="black")
    y += 30
    for key, value in FAKE_CLAIM.items():
        label = key.replace("_", " ").upper()
        draw.text((20, y), f"{label}: {value}", fill="black")
        y += 25

    draw.text((20, y + 10), "*** SYNTHETIC TEST DATA - NOT A REAL CLAIM ***", fill="black")
    img.save(path)


async def run_test():
    from app.ocr.tesseract import TesseractProvider

    with tempfile.TemporaryDirectory() as tmpdir:
        # Try PDF first, fall back to PNG
        try:
            from fpdf import FPDF  # noqa: F401
            test_file = os.path.join(tmpdir, "synthetic_claim.pdf")
            generate_test_pdf(test_file)
            file_type = "PDF"
        except ImportError:
            test_file = os.path.join(tmpdir, "synthetic_claim.png")
            generate_test_image(test_file)
            file_type = "PNG"

        print(f"Generated synthetic {file_type} test file: {test_file}")

        from pathlib import Path
        provider = TesseractProvider()
        mime = "application/pdf" if file_type == "PDF" else "image/png"
        result = await provider.extract(Path(test_file), mime)

        print(f"\n--- OCR Result ---")
        print(f"Provider:    {result.provider}")
        print(f"Confidence:  {result.confidence:.3f}")
        print(f"Page count:  {result.page_count}")
        print(f"Text length: {len(result.text)} chars")
        structured = getattr(result, 'structured', None) or {}
        print(f"\nStructured fields extracted: {list(structured.keys())}")

        print(f"\nOCR text preview (first 400 chars):")
        print(result.text[:400])

        # Validate expected content appears in OCR output
        checks = [
            ("DOE" in result.text.upper() or "JANE" in result.text.upper(), "Patient name"),
            ("99213" in result.text or "9 9 2 1 3" in result.text, "CPT code"),
            ("M54" in result.text.upper(), "Diagnosis code"),
            (result.confidence > 0.0, "Non-zero confidence"),
            (result.page_count >= 1, "At least one page"),
        ]

        print(f"\n--- Validation ---")
        all_passed = True
        for passed, label in checks:
            status = "PASS" if passed else "FAIL"
            print(f"  [{status}] {label}")
            if not passed:
                all_passed = False

        if all_passed:
            print("\nAll checks passed — OCR pipeline is functional.")
        else:
            print("\nSome checks failed — review OCR output above.")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_test())
