from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OcrResult:
    text: str
    structured: dict = field(default_factory=dict)
    confidence: float = 0.0
    provider: str = ""
    page_count: int = 0


class OcrProvider(ABC):
    @abstractmethod
    async def extract(self, file_path: str) -> OcrResult:
        """Extract text and structured data from a document."""
        ...
