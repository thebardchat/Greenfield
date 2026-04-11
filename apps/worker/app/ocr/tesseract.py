from app.ocr.base import OcrProvider, OcrResult


class TesseractProvider(OcrProvider):
    """Local Tesseract OCR with CMS-1500/UB-04 template overlay.

    Uses pdf2image for PDF rasterization at 300 DPI, then
    pytesseract for character recognition. For CMS-1500 forms,
    crops known field regions for higher per-field accuracy.
    """

    async def extract(self, file_path: str) -> OcrResult:
        ...
