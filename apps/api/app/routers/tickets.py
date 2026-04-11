from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_tickets():
    ...


@router.post("/")
async def create_ticket():
    ...


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: str):
    ...


@router.patch("/{ticket_id}")
async def update_ticket(ticket_id: str):
    ...


@router.post("/{ticket_id}/comments")
async def add_comment(ticket_id: str):
    ...


@router.get("/{ticket_id}/comments")
async def list_comments(ticket_id: str):
    ...
