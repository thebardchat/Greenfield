from app.ocr.base import OcrProvider, OcrResult


class DocumentAIProvider(OcrProvider):
    """Google Document AI cloud OCR fallback.

    Used when Tesseract confidence falls below threshold.
    Requires GOOGLE_APPLICATION_CREDENTIALS and DOCUMENT_AI_PROCESSOR_ID.
    """

    async def extract(self, file_path: str) -> OcrResult:
        ...
