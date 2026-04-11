"""OCR pipeline task.

Flow:
1. Load document from storage
2. Run Tesseract local OCR
3. Check confidence against threshold
4. If below threshold and cloud provider configured, run cloud OCR fallback
5. Store results in claim_documents
6. Enqueue auto-flag task if Cruncher is configured
7. Update claim status to ready_for_review or ocr_failed
"""


async def process_document(ctx, document_id: str):
    """Main OCR pipeline entry point."""
    ...
