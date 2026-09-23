"""Weighted risk fusion (Module 6). Weights: checksum 0.16, forensics
0.16, deepfake 0.10, blacklist 0.16, face match 0.12, identity graph 0.08,
liveness 0.10, duplicate_document 0.12, face_detection 0.10,
citizen_registry 0.14.

If a signal wasn't supplied (e.g. liveness/deepfake when no live capture
was taken, or either provider reporting NOT_IMPLEMENTED), its weight is
dropped and the remaining weights are renormalized to sum to 1, rather
than silently treating a missing signal as "zero risk" or shrinking the
maximum possible score. Hard overrides (a HIGH-severity EXACT blacklist
hit, a multi-identity cluster, a HIGH-severity front/back cross-check
failure, the same document number reused under a different declared
name, or a document number on file for a different citizen-registry
identity) force HIGH_RISK/MANUAL_REVIEW regardless of the weighted score —
these are the cases a checkpoint cannot afford to average away. An
ordinary repeat crossing on the same document under the *same* name is
explicitly NOT penalized — SSB's checkpoints are open, treaty-based
borders where that is routine, not fraud (see CLAUDE.md).
"""
from app.services.citizen_registry.base import CitizenRegistryResult
from app.services.deepfake.base import DeepfakeResult
from app.services.duplicate.base import DuplicateDocumentResult
from app.services.face.base import FaceDetectionResult, FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskEngine, RiskResult, RiskSignalBreakdown
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult

_WEIGHTS = {
    "checksum": 0.16,
    "forensics": 0.16,
    "deepfake": 0.10,
    "blacklist": 0.16,
    "face_match": 0.12,
    "identity_graph": 0.08,
    "liveness": 0.10,
    "duplicate_document": 0.12,
    "face_detection": 0.10,
    "citizen_registry": 0.14,
}
_FUZZY_CONFIDENCE_MULTIPLIER = 0.5
_LOW_RISK_CEILING = 20
_MEDIUM_RISK_CEILING = 55


def active_risk_config() -> dict:
    """Read-only view of the actual constants above — for the Admin
    Settings page. There's no persistence layer for these yet (they're
    still hardcoded here), so this is honestly a *display* of the real
    active configuration, not an editable settings store — see this
    module's docstring for why each weight is what it is."""
    return {
        "weights": dict(_WEIGHTS),
        "low_risk_ceiling": _LOW_RISK_CEILING,
        "medium_risk_ceiling": _MEDIUM_RISK_CEILING,
    }


def _severity_risk(severity: str) -> float:
    return {"LOW": 0.3, "MEDIUM": 0.6, "HIGH": 1.0}.get(severity.upper(), 0.6)


def _checksum_risk(result: ValidationResult) -> tuple[float, str, dict | None]:
    """Calculate risk from validation findings.

    Only actual validation failures (FAIL status) contribute to risk.
    NOT_AVAILABLE, UNCERTAIN, NOT_EVALUATED do not increase risk —
    those are extraction limitations, not validation failures.
    """
    failed = [f for f in result.findings if f.status == "FAIL"]
    if not failed:
        # Check if there are uncertain/missing fields (for informational reason)
        uncertain = [f for f in result.findings if f.status in ("NOT_AVAILABLE", "UNCERTAIN", "NOT_EVALUATED")]
        if uncertain:
            return 0.0, f"No validation failures ({len(uncertain)} fields need officer review)", None
        return 0.0, "All validation checks passed", None
    worst = max(failed, key=lambda f: _severity_risk(f.severity))
    return _severity_risk(worst.severity), f"{worst.check}: {worst.reason}", worst.location


def _forensics_risk(result: TamperingResult) -> tuple[float, str, dict | None]:
    if not result.findings:
        return result.tampering_risk, "no forensic findings", None
    finding = result.findings[0]
    return result.tampering_risk, finding.reason, finding.location


def _blacklist_risk(result: RegistryLookupResult) -> tuple[float, str, dict | None]:
    if not result.hits:
        return 0.0, "no registry hits", None
    best_hit, best_risk = None, -1.0
    for hit in result.hits:
        multiplier = 1.0 if hit.match_type == "EXACT" else _FUZZY_CONFIDENCE_MULTIPLIER
        risk = _severity_risk(hit.severity) * multiplier
        if risk > best_risk:
            best_hit, best_risk = hit, risk
    reason = (
        f"{best_hit.match_type} match on {best_hit.matched_field} vs registry entry "
        f"{best_hit.full_name!r} ({best_hit.registry_reason}), confidence {best_hit.confidence}"
    )
    return best_risk, reason, None


def _face_risk(result: FaceMatchResult) -> tuple[float, str, dict | None]:
    if not result.match:
        # Mismatch is a serious security concern — scale risk by how far
        # below threshold the similarity is: 0.42 threshold, 0.1 similarity
        # should produce near-maximum risk.
        risk = min(1.0, 0.6 + (0.42 - result.similarity) * 1.5)
        return max(0.5, risk), result.reason, result.location
    # Match: risk inversely proportional to similarity strength
    return max(0.0, 0.3 - result.similarity * 0.5), result.reason, result.location


def _identity_graph_risk(result: IdentityGraphResult) -> tuple[float, str, dict | None]:
    risk = 1.0 if result.status == "CLUSTER_FOUND" else 0.0
    return risk, result.reason, None


def _liveness_risk(result: LivenessResult) -> tuple[float, str, dict | None]:
    return result.score or 0.0, result.reason, None


def _face_detection_risk(result: FaceDetectionResult) -> tuple[float, str, dict | None]:
    if result.status == "NO_FACE":
        return 0.9, result.reason, None
    if result.status == "MULTIPLE_FACES":
        return 0.8, result.reason, result.faces[0].location if result.faces else None
    face = result.faces[0]
    if face.touches_edge:
        return 0.4, result.reason, face.location
    return 0.0, result.reason, None


def _citizen_registry_risk(result: CitizenRegistryResult) -> tuple[float, str, dict | None]:
    if result.status == "MISMATCH":
        return 1.0, result.reason, None
    if result.status == "REVOKED_MATCH":
        return 0.9, result.reason, None
    if result.status == "NO_RECORD":
        # Document not found in registry — a real security concern. At a
        # border checkpoint an unrecognized document warrants officer review.
        return 0.4, result.reason or "Document/person not found in citizen registry — identity cannot be verified against known records", None
    # MATCH — positive identity confirmation
    return 0.0, result.reason, None


def _duplicate_document_risk(result: DuplicateDocumentResult) -> tuple[float, str, dict | None]:
    if result.status == "DIFFERENT_IDENTITY_REUSE":
        return 1.0, result.reason, None
    # NO_MATCH and SAME_IDENTITY_REUSE (a routine repeat crossing) are
    # both zero risk — only a different declared identity on the same
    # document number is a real signal here.
    return 0.0, result.reason, None


class DefaultRiskEngine(RiskEngine):
    def score(
        self,
        validation_result: ValidationResult | None = None,
        tampering_result: TamperingResult | None = None,
        deepfake_result: DeepfakeResult | None = None,
        registry_result: RegistryLookupResult | None = None,
        face_result: FaceMatchResult | None = None,
        identity_graph_result: IdentityGraphResult | None = None,
        liveness_result: LivenessResult | None = None,
        duplicate_document_result: DuplicateDocumentResult | None = None,
        face_detection_result: FaceDetectionResult | None = None,
        citizen_registry_result: CitizenRegistryResult | None = None,
    ) -> RiskResult:
        components: dict[str, tuple[float, str, dict | None]] = {}

        if validation_result is not None:
            components["checksum"] = _checksum_risk(validation_result)
        if tampering_result is not None:
            components["forensics"] = _forensics_risk(tampering_result)
        if deepfake_result is not None and deepfake_result.status != "NOT_IMPLEMENTED":
            components["deepfake"] = (deepfake_result.score or 0.0, deepfake_result.reason, None)
        if registry_result is not None:
            components["blacklist"] = _blacklist_risk(registry_result)
        if face_result is not None:
            components["face_match"] = _face_risk(face_result)
        if identity_graph_result is not None:
            components["identity_graph"] = _identity_graph_risk(identity_graph_result)
        if liveness_result is not None and liveness_result.status != "NOT_IMPLEMENTED":
            components["liveness"] = _liveness_risk(liveness_result)
        if duplicate_document_result is not None:
            components["duplicate_document"] = _duplicate_document_risk(duplicate_document_result)
        if face_detection_result is not None:
            components["face_detection"] = _face_detection_risk(face_detection_result)
        if citizen_registry_result is not None:
            components["citizen_registry"] = _citizen_registry_risk(citizen_registry_result)

        if not components:
            return RiskResult(
                score=0, level="LOW_RISK", decision="CLEAR", top_reason="no signals were supplied", breakdown=[]
            )

        total_weight = sum(_WEIGHTS[signal] for signal in components)
        breakdown = []
        weighted_sum = 0.0
        for signal, (risk, reason, location) in components.items():
            normalized_weight = _WEIGHTS[signal] / total_weight
            contribution = normalized_weight * risk
            weighted_sum += contribution
            breakdown.append(
                RiskSignalBreakdown(
                    signal=signal,
                    weight=round(normalized_weight, 4),
                    raw_risk=round(risk, 4),
                    contribution=round(contribution, 4),
                    reason=reason,
                    location=location,
                )
            )
        breakdown.sort(key=lambda b: b.contribution, reverse=True)
        score = round(weighted_sum * 100)

        override_level, override_decision, override_reason = self._hard_overrides(
            registry_result, identity_graph_result, validation_result,
            duplicate_document_result, citizen_registry_result,
        )
        if override_level is not None:
            return RiskResult(
                score=max(score, 71),
                level=override_level,
                decision=override_decision,
                top_reason=override_reason,
                breakdown=breakdown,
            )

        level = self._level_for_score(score)
        top = breakdown[0]
        # Face mismatch is a headline condition, but at its normal weight it
        # is averaged away by a run of clean signals — so a below-threshold
        # match is floored to review. It is deliberately NOT escalated to a
        # hard HIGH: the face embedding is a HOG descriptor, and the same
        # person photographed on-device against a small document photo can
        # score well below a threshold that different people also miss, so a
        # "strong mismatch" verdict would not be honest. The officer sees the
        # exact similarity value and decides.
        if face_result is not None and not face_result.match:
            # Face mismatch is a critical security signal — always escalate
            if face_result.similarity < 0.25:
                level = "HIGH_RISK"
                score = max(score, _MEDIUM_RISK_CEILING)
            elif level == "LOW_RISK":
                level = "MEDIUM_RISK"
                score = max(score, _LOW_RISK_CEILING)
            top = next(b for b in breakdown if b.signal == "face_match")
        if (
            level == "LOW_RISK"
            and face_detection_result is not None
            and face_detection_result.status in ("NO_FACE", "MULTIPLE_FACES")
        ):
            level = "MEDIUM_RISK"
            score = max(score, _LOW_RISK_CEILING)
            top = next(b for b in breakdown if b.signal == "face_detection")
        decision = "CLEAR" if level == "LOW_RISK" else "MANUAL_REVIEW"
        return RiskResult(
            score=score, level=level, decision=decision, top_reason=f"{top.signal}: {top.reason}", breakdown=breakdown
        )

    def _level_for_score(self, score: int) -> str:
        if score < _LOW_RISK_CEILING:
            return "LOW_RISK"
        if score < _MEDIUM_RISK_CEILING:
            return "MEDIUM_RISK"
        return "HIGH_RISK"

    def _hard_overrides(
        self,
        registry_result: RegistryLookupResult | None,
        identity_graph_result: IdentityGraphResult | None,
        validation_result: ValidationResult | None,
        duplicate_document_result: DuplicateDocumentResult | None = None,
        citizen_registry_result: CitizenRegistryResult | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        if citizen_registry_result is not None and citizen_registry_result.status == "MISMATCH":
            return (
                "HIGH_RISK",
                "MANUAL_REVIEW",
                f"hard override: {citizen_registry_result.reason}",
            )
        if duplicate_document_result is not None and duplicate_document_result.status == "DIFFERENT_IDENTITY_REUSE":
            return (
                "HIGH_RISK",
                "MANUAL_REVIEW",
                f"hard override: {duplicate_document_result.reason}",
            )
        if registry_result is not None:
            for hit in registry_result.hits:
                if hit.match_type == "EXACT" and hit.severity == "HIGH":
                    return (
                        "HIGH_RISK",
                        "MANUAL_REVIEW",
                        f"hard override: EXACT blacklist hit on {hit.full_name!r} ({hit.registry_reason})",
                    )
        if identity_graph_result is not None and identity_graph_result.status == "CLUSTER_FOUND":
            return (
                "HIGH_RISK",
                "MANUAL_REVIEW",
                f"hard override: multi-identity cluster detected — {identity_graph_result.reason}",
            )
        if validation_result is not None:
            for finding in validation_result.findings:
                if finding.status == "FAIL" and finding.severity == "HIGH":
                    # Front/back disagreement vs. the document failing its own
                    # validity rules (expired, invalid document number,
                    # check-digit failure) — a single such failure is enough
                    # for officer review; averaging it against clean signals
                    # would bury it.
                    what = (
                        "severe front/back mismatch"
                        if finding.check.startswith("cross_check")
                        else "document failed a validity check"
                    )
                    return "HIGH_RISK", "MANUAL_REVIEW", f"hard override: {what} — {finding.reason}"
        return None, None, None
