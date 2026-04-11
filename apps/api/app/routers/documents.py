from fastapi import APIRouter

router = APIRouter()


@router.post("/upload")
async def upload_document():
    """Upload PDF, compute checksum, enqueue OCR job."""
    ...


@router.get("/{document_id}")
async def get_document(document_id: str):
    ...


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """Serve file through API with RBAC check + audit log."""
    ...


@router.get("/{document_id}/ocr")
async def get_ocr_results(document_id: str):
    """Return OCR text, structured data, and confidence."""
    ...
