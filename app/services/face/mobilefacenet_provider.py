"""Face matching via MobileFaceNet (InsightFace buffalo_sc model).

MobileFaceNet is a lightweight face recognition model (~4MB) that produces
128-dim embeddings. We use InsightFace's pre-trained buffalo_sc model pack
which includes both a face detector (SCRFD) and MobileFaceNet recognizer.

This replaces the HOG descriptor (embedding.py) with a real deep-learning
face embedding — significantly more accurate for cross-condition matching
(document photo vs. live selfie with different lighting/angle/resolution).
"""
import io
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from app.services.face.base import FaceMatchResult, FaceProvider

logger = logging.getLogger("pramaan.face")

_MATCH_THRESHOLD = 0.50
_insightface_app = None


def _get_insightface_app():
    global _insightface_app
    if _insightface_app is not None:
        return _insightface_app
    try:
        from insightface.app import FaceAnalysis
        app = FaceAnalysis(
            name="buffalo_sc",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _insightface_app = app
        logger.info("MobileFaceNet (buffalo_sc) loaded successfully")
        return app
    except Exception as e:
        logger.warning("InsightFace unavailable: %s — falling back to HOG", e)
        return None


def _image_to_bgr(image_bytes: bytes) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def _extract_embedding_insightface(app, bgr: np.ndarray) -> np.ndarray | None:
    faces = app.get(bgr)
    if not faces:
        return None
    best = max(faces, key=lambda f: f.det_score)
    return best.normed_embedding


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = (np.linalg.norm(a) * np.linalg.norm(b)) or 1e-9
    return float(dot / norm)


def mobilefacenet_match(
    document_embedding: list[float],
    live_embedding: list[float],
) -> FaceMatchResult:
    """Compare two MobileFaceNet embeddings (128-dim vectors)."""
    a = np.asarray(document_embedding, dtype=np.float32)
    b = np.asarray(live_embedding, dtype=np.float32)
    if a.shape != b.shape or a.size == 0:
        return FaceMatchResult(
            match=False, similarity=0.0, confidence=0.0,
            reason="embedding dimension mismatch or empty vector",
            location=None,
        )
    sim = _cosine_similarity(a, b)
    match = sim >= _MATCH_THRESHOLD
    confidence = max(0.0, min(1.0, (sim + 1.0) / 2.0))
    return FaceMatchResult(
        match=match,
        similarity=round(sim, 4),
        confidence=round(confidence, 4),
        reason=(
            f"MobileFaceNet cosine similarity {sim:.4f} vs threshold {_MATCH_THRESHOLD}: "
            + ("match" if match else "no match — faces appear to be different persons"
               if sim < 0.2 else "no match — below confidence threshold")
        ),
        location=None,
    )


def extract_mobilefacenet_embedding(image_bytes: bytes) -> list[float] | None:
    """Extract a 128-dim MobileFaceNet embedding from an image.
    Returns None if no face detected or InsightFace unavailable."""
    app = _get_insightface_app()
    if app is None:
        return None
    bgr = _image_to_bgr(image_bytes)
    emb = _extract_embedding_insightface(app, bgr)
    if emb is None:
        return None
    return emb.tolist()


class MobileFaceNetProvider(FaceProvider):
    """Face matching using MobileFaceNet via InsightFace.
    Falls back to HOG (ClassicalFaceProvider) if InsightFace is unavailable.
    Runs quality checks on both images — returns inconclusive if quality
    is too poor, rather than a false mismatch."""

    def __init__(self):
        self._app = _get_insightface_app()

    def verify(self, document_face: bytes, presented_face: bytes) -> FaceMatchResult:
        from app.services.face.quality import assess_quality

        doc_quality = assess_quality(document_face)
        live_quality = assess_quality(presented_face)
        all_issues = (
            [f"document: {i}" for i in doc_quality.issues]
            + [f"live: {i}" for i in live_quality.issues]
        )

        if self._app is None:
            self._app = _get_insightface_app()

        if self._app is None:
            from app.services.face.classical_provider import ClassicalFaceProvider
            logger.warning("MobileFaceNet unavailable, using HOG fallback")
            return ClassicalFaceProvider().verify(document_face, presented_face)

        doc_bgr = _image_to_bgr(document_face)
        live_bgr = _image_to_bgr(presented_face)

        doc_emb = _extract_embedding_insightface(self._app, doc_bgr)
        live_emb = _extract_embedding_insightface(self._app, live_bgr)

        if doc_emb is None:
            if not doc_quality.is_sufficient:
                return FaceMatchResult(
                    match=False, similarity=0.0, confidence=0.0,
                    inconclusive=True,
                    quality_issues=all_issues,
                    reason="INCONCLUSIVE: no face detected in document image — "
                           f"quality issues: {'; '.join(doc_quality.issues) or 'none detected'}",
                    location=None,
                )
            return FaceMatchResult(
                match=False, similarity=0.0, confidence=0.0,
                quality_issues=all_issues,
                reason="MobileFaceNet: no face detected in document image",
                location=None,
            )

        if live_emb is None:
            if not live_quality.is_sufficient:
                return FaceMatchResult(
                    match=False, similarity=0.0, confidence=0.0,
                    inconclusive=True,
                    quality_issues=all_issues,
                    reason="INCONCLUSIVE: no face detected in live capture — "
                           f"quality issues: {'; '.join(live_quality.issues) or 'none detected'}",
                    location=None,
                )
            return FaceMatchResult(
                match=False, similarity=0.0, confidence=0.0,
                quality_issues=all_issues,
                reason="MobileFaceNet: no face detected in live capture",
                location=None,
            )

        sim = _cosine_similarity(doc_emb, live_emb)
        match = sim >= _MATCH_THRESHOLD
        confidence = max(0.0, min(1.0, (sim + 1.0) / 2.0))

        if not match and (not doc_quality.is_sufficient or not live_quality.is_sufficient):
            return FaceMatchResult(
                match=False,
                similarity=round(sim, 4),
                confidence=round(confidence, 4),
                inconclusive=True,
                quality_issues=all_issues,
                reason=f"INCONCLUSIVE: similarity {sim:.4f} below threshold "
                       f"{_MATCH_THRESHOLD}, but image quality is poor — "
                       f"officer review recommended rather than automatic mismatch",
                location=None,
            )

        if match:
            reason = (
                f"MobileFaceNet match confirmed: similarity {sim:.4f} "
                f"(threshold {_MATCH_THRESHOLD})"
            )
        elif sim < 0.15:
            reason = (
                f"MobileFaceNet: strong mismatch, similarity {sim:.4f} — "
                f"faces appear to be different persons"
            )
        elif sim < _MATCH_THRESHOLD:
            reason = (
                f"MobileFaceNet: similarity {sim:.4f} below threshold "
                f"{_MATCH_THRESHOLD} — manual verification recommended"
            )
        else:
            reason = f"MobileFaceNet: similarity {sim:.4f}"

        return FaceMatchResult(
            match=match,
            similarity=round(sim, 4),
            confidence=round(confidence, 4),
            quality_issues=all_issues,
            reason=reason,
            location=None,
        )
