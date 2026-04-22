"""OCR provider registry."""
from .base import OcrProvider, OcrResult, OcrStatus
from .tesseract import TesseractProvider

__all__ = ["OcrProvider", "OcrResult", "OcrStatus", "TesseractProvider"]


def get_provider(name: str = "tesseract") -> OcrProvider:
    """Return an OCR provider by name. Extend as cloud providers are added."""
    providers: dict[str, type[OcrProvider]] = {
        "tesseract": TesseractProvider,
    }
    cls = providers.get(name)
    if cls is None:
        raise ValueError(f"Unknown OCR provider: {name!r}. Available: {list(providers)}")
    return cls()
