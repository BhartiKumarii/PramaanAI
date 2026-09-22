from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import (
    admin,
    audit,
    auth,
    blockchain,
    cases,
    checkpoints,
    comprehensive_verification,
    dashboard,
    dashboard_risk_cases,
    devices,
    documents,
    face,
    identity,
    images,
    network,
    registry,
    system,
    testing,
    verification,
)
from app.core.config import get_settings
from app.utils.logging import setup_logging

setup_logging()

settings = get_settings()

app = FastAPI(
    title="PramaanAI",
    description=(
        "Privacy-preserving AI-powered identity and travel-document screening "
        "backend (hackathon prototype — not a production border-security system)."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url=None,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(checkpoints.router)
app.include_router(comprehensive_verification.router)
app.include_router(dashboard.router)
app.include_router(dashboard_risk_cases.router)
app.include_router(devices.router)
app.include_router(admin.router)
app.include_router(audit.router)
app.include_router(network.router)
app.include_router(system.router)
app.include_router(documents.router)
app.include_router(face.router)
app.include_router(registry.router)
app.include_router(identity.router)
app.include_router(images.router)
app.include_router(verification.router)
app.include_router(blockchain.router)
app.include_router(testing.router)


@app.get("/health", tags=["system"], summary="Liveness check")
def health() -> dict[str, str]:
    return {"status": "ok"}
