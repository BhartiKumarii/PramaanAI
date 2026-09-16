from fastapi import FastAPI

from app.api.routes import (
    admin,
    auth,
    blockchain,
    cases,
    checkpoints,
    dashboard,
    devices,
    documents,
    face,
    identity,
    registry,
    system,
    verification,
)
from app.utils.logging import setup_logging

setup_logging()

app = FastAPI(
    title="PramaanAI",
    description=(
        "Privacy-preserving AI-powered identity and travel-document screening "
        "backend (hackathon prototype — not a production border-security system)."
    ),
    version="0.1.0",
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(checkpoints.router)
app.include_router(dashboard.router)
app.include_router(devices.router)
app.include_router(admin.router)
app.include_router(system.router)
app.include_router(documents.router)
app.include_router(face.router)
app.include_router(registry.router)
app.include_router(identity.router)
app.include_router(verification.router)
app.include_router(blockchain.router)


@app.get("/health", tags=["system"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}
