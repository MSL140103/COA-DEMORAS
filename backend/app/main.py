from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import calculations, documents, overrides, sof_events, voyages
from app.infrastructure.db.config import settings

app = FastAPI(
    title="Laytime & Demurrage API",
    description="Deterministic laytime/demurrage calculation engine — see docs/architecture/SYSTEM_ARCHITECTURE.md",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # No cookies/auth headers are used anywhere in MVP1, and the deployed frontend
    # talks to this API same-origin through a server-side proxy anyway — CORS here
    # only matters for direct API testing (curl, Swagger UI from another origin).
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(voyages.router)
app.include_router(sof_events.router)
app.include_router(documents.router)
app.include_router(calculations.router)
app.include_router(overrides.router)


@app.get("/health")
def health():
    return {"status": "ok"}
