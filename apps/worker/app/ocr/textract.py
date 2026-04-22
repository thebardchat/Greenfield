from app.ocr.base import OcrProvider, OcrResult


class TextractProvider(OcrProvider):
    """AWS Textract cloud OCR provider.

    Highest accuracy on medical forms but most expensive.
    Requires AWS credentials and BAA.
    """

    async def extract(self, file_path: str) -> OcrResult:
        ...
