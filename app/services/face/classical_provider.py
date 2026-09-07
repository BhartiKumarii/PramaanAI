"""Face verification via the classical HOG-style embedding (see
embedding.py) and real cosine similarity — no separate face-detection
step: the document photo and the live capture are both treated as
already face-framed images (a real ID photo and a selfie capture both
are, by construction), so `location` is null rather than a detected
bounding box. A mediapipe-based detector was attempted for this but its
install kept failing on flaky large-dependency downloads (matplotlib's
fontTools wheel) for a piece that isn't this module's core requirement;
not worth blocking the actually-required embedding+similarity computation
on it.
"""
from app.services.face.base import FaceMatchResult, FaceProvider
from app.services.face.embedding import cosine_similarity, extract_embedding

# Heuristic for this classical descriptor — not calibrated against a
# labeled dataset, documented as such rather than presented as a
# validated biometric threshold.
_MATCH_THRESHOLD = 0.75


class ClassicalFaceProvider(FaceProvider):
    def verify(self, document_face: bytes, presented_face: bytes) -> FaceMatchResult:
        document_embedding = extract_embedding(document_face)
        presented_embedding = extract_embedding(presented_face)
        similarity = cosine_similarity(document_embedding, presented_embedding)
        match = similarity >= _MATCH_THRESHOLD
        confidence = max(0.0, min(1.0, (similarity + 1.0) / 2.0))

        return FaceMatchResult(
            match=match,
            similarity=round(similarity, 4),
            confidence=round(confidence, 4),
            reason=(
                f"cosine similarity {similarity:.4f} vs match threshold {_MATCH_THRESHOLD}: "
                + ("above threshold, match" if match else "below threshold, no match")
            ),
            location=None,
        )
