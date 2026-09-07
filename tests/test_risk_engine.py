from app.services.deepfake.base import DeepfakeResult
from app.services.face.base import FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.registry.base import RegistryHit, RegistryLookupResult
from app.services.risk.engine import DefaultRiskEngine
from app.services.tampering.base import TamperingFinding, TamperingResult
from app.services.validation.base import ValidationFinding, ValidationResult

_ENGINE = DefaultRiskEngine()

_CLEAN_VALIDATION = ValidationResult(
    status="PASS",
    findings=[ValidationFinding(check="expiry", status="PASS", severity="LOW", reason="not expired")],
)
_NO_HIT_REGISTRY = RegistryLookupResult(status="NO_HIT", hits=[])
_NO_CLUSTER_IDENTITY = IdentityGraphResult(status="NO_CLUSTER", cluster_size=1, members=[], reason="single record")
_NOT_IMPLEMENTED_DEEPFAKE = DeepfakeResult(status="NOT_IMPLEMENTED", score=None, reason="no classifier wired up")


def _tampering(risk: float) -> TamperingResult:
    return TamperingResult(
        tampering_risk=risk,
        findings=[TamperingFinding(type="ela_compression_anomaly", confidence=risk, reason="test", location=None)],
    )


def _face(confidence: float) -> FaceMatchResult:
    return FaceMatchResult(
        match=confidence >= 0.75, similarity=confidence, confidence=confidence, reason="test", location=None
    )


def test_no_signals_supplied_scores_zero_and_clears():
    result = _ENGINE.score()
    assert result.score == 0
    assert result.level == "LOW_RISK"
    assert result.decision == "CLEAR"
    assert result.breakdown == []


def test_weighted_fusion_with_missing_deepfake_renormalizes_weights():
    result = _ENGINE.score(
        validation_result=_CLEAN_VALIDATION,
        tampering_result=_tampering(0.5),
        registry_result=_NO_HIT_REGISTRY,
        face_result=_face(0.9),
        identity_graph_result=_NO_CLUSTER_IDENTITY,
        # deepfake_result intentionally omitted
    )
    assert result.score == 14
    assert result.level == "LOW_RISK"
    assert result.decision == "CLEAR"
    weight_sum = sum(b.weight for b in result.breakdown)
    assert abs(weight_sum - 1.0) < 0.01
    assert result.breakdown[0].signal == "forensics"
    assert "forensics" in result.top_reason


def test_deepfake_not_implemented_is_excluded_like_missing():
    with_none = _ENGINE.score(validation_result=_CLEAN_VALIDATION, tampering_result=_tampering(0.5))
    with_stub = _ENGINE.score(
        validation_result=_CLEAN_VALIDATION,
        tampering_result=_tampering(0.5),
        deepfake_result=_NOT_IMPLEMENTED_DEEPFAKE,
    )
    assert with_none.score == with_stub.score
    assert {b.signal for b in with_stub.breakdown} == {b.signal for b in with_none.breakdown}


def test_exact_high_severity_blacklist_hit_hard_overrides_to_high_risk():
    registry_result = RegistryLookupResult(
        status="HIT",
        hits=[
            RegistryHit(
                document_number="X1",
                full_name="SOMEONE",
                registry_reason="watchlist",
                severity="HIGH",
                match_type="EXACT",
                confidence=1.0,
                matched_field="document_number",
                explanation="test",
            )
        ],
    )
    result = _ENGINE.score(
        validation_result=_CLEAN_VALIDATION,
        tampering_result=_tampering(0.0),
        registry_result=registry_result,
        face_result=_face(0.99),
        identity_graph_result=_NO_CLUSTER_IDENTITY,
    )
    assert result.level == "HIGH_RISK"
    assert result.decision == "MANUAL_REVIEW"
    assert "hard override" in result.top_reason
    assert "blacklist" in result.top_reason


def test_fuzzy_blacklist_hit_does_not_hard_override():
    registry_result = RegistryLookupResult(
        status="HIT",
        hits=[
            RegistryHit(
                document_number="X1",
                full_name="SOMEONE",
                registry_reason="watchlist",
                severity="HIGH",
                match_type="FUZZY",
                confidence=0.85,
                matched_field="full_name",
                explanation="test",
            )
        ],
    )
    result = _ENGINE.score(
        validation_result=_CLEAN_VALIDATION,
        tampering_result=_tampering(0.0),
        registry_result=registry_result,
        face_result=_face(0.99),
        identity_graph_result=_NO_CLUSTER_IDENTITY,
    )
    assert "hard override" not in result.top_reason
    # Fuzzy match still contributes real risk, just weighted+multiplied, not an override.
    blacklist_entry = next(b for b in result.breakdown if b.signal == "blacklist")
    assert blacklist_entry.raw_risk == 0.5  # HIGH severity (1.0) * 0.5 fuzzy multiplier


def test_multi_identity_cluster_hard_overrides_to_high_risk():
    cluster_result = IdentityGraphResult(
        status="CLUSTER_FOUND", cluster_size=2, members=[], reason="two names, one face"
    )
    result = _ENGINE.score(
        validation_result=_CLEAN_VALIDATION,
        tampering_result=_tampering(0.0),
        registry_result=_NO_HIT_REGISTRY,
        face_result=_face(0.99),
        identity_graph_result=cluster_result,
    )
    assert result.level == "HIGH_RISK"
    assert result.decision == "MANUAL_REVIEW"
    assert "multi-identity" in result.top_reason


def test_severe_cross_check_mismatch_hard_overrides_to_high_risk():
    validation_result = ValidationResult(
        status="FAIL",
        findings=[
            ValidationFinding(
                check="cross_check_document_number",
                status="FAIL",
                severity="HIGH",
                reason="front OCR document number 'Z0' vs MRZ document number 'N1': mismatch",
            )
        ],
    )
    result = _ENGINE.score(
        validation_result=validation_result,
        tampering_result=_tampering(0.0),
        registry_result=_NO_HIT_REGISTRY,
        face_result=_face(0.99),
        identity_graph_result=_NO_CLUSTER_IDENTITY,
    )
    assert result.level == "HIGH_RISK"
    assert result.decision == "MANUAL_REVIEW"
    assert "cross_check" in result.top_reason or "mismatch" in result.top_reason
