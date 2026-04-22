from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.middleware.audit import AuditMiddleware
from app.routers import (
    auth,
    claims,
    credentials,
    cruncher,
    documents,
    facilities,
    organizations,
    patients,
    reports,
    tickets,
)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs" if settings.app_env == "development" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HIPAA audit trail — logs every request (fire-and-forget, non-blocking)
app.add_middleware(AuditMiddleware)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(organizations.router, prefix="/api/organizations", tags=["organizations"])
app.include_router(facilities.router, prefix="/api/facilities", tags=["facilities"])
app.include_router(patients.router, prefix="/api/patients", tags=["patients"])
app.include_router(claims.router, prefix="/api/claims", tags=["claims"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(tickets.router, prefix="/api/tickets", tags=["tickets"])
app.include_router(credentials.router, prefix="/api/credentials", tags=["credentials"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])
app.include_router(cruncher.router, prefix="/api/cruncher", tags=["cruncher"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}
