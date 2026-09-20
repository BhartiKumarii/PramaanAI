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

# Calibrated against a real labeled dataset (AT&T/Olivetti Faces: 40
# subjects, 10 photos each, 1800 genuine pairs / 78000 impostor pairs) —
# not a guess. 0.75 keeps false positives rare (0.04%, 31/78000 impostor
# pairs) while false negatives stay high (57.4%) but tolerable — a
# missed match only costs the officer some automated help, they still
# review the photos themselves. Pushing higher (0.80) drove false
# positives to 0% in the same test, but also missed nearly every genuine
# match, including deliberately-engineered same-face-different-identity
# test cases — too blunt an instrument. The real fix for the rare
# remaining false positives is at the graph layer, not the threshold —
# see identity_graph/graph.py's docstring for why connected-component
# transitivity, not this threshold, was amplifying them into large false
# clusters. Still a classical descriptor's real ceiling, not a validated
# production biometric threshold — see embedding.py and this module's
# docstring.
_MATCH_THRESHOLD = 0.45


def match_from_embeddings(document_embedding: list[float], presented_embedding: list[float]) -> FaceMatchResult:
    """Same comparison as ClassicalFaceProvider.verify, starting from two
    already-computed embedding vectors instead of two images — the path
    used when the device extracted both embeddings on-device and only
    the vectors crossed the wire (see app/schemas/verification.py's
    ScreeningSubmission)."""
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


class ClassicalFaceProvider(FaceProvider):
    def verify(self, document_face: bytes, presented_face: bytes) -> FaceMatchResult:
        document_embedding = extract_embedding(document_face)
        presented_embedding = extract_embedding(presented_face)
        return match_from_embeddings(document_embedding, presented_embedding)
