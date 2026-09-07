from fastapi import FastAPI

from app.api.routes import auth, blockchain, documents, face, identity, registry, verification
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
app.include_router(documents.router)
app.include_router(face.router)
app.include_router(registry.router)
app.include_router(identity.router)
app.include_router(verification.router)
app.include_router(blockchain.router)


@app.get("/health", tags=["system"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}
