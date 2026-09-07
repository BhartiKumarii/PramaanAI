"""Weighted risk fusion (Module 6). Weights: checksum 0.18, forensics
0.18, deepfake 0.12, blacklist 0.18, face match 0.14, identity graph 0.08,
liveness 0.12.

If a signal wasn't supplied (e.g. liveness/deepfake when no live capture
was taken, or either provider reporting NOT_IMPLEMENTED), its weight is
dropped and the remaining weights are renormalized to sum to 1, rather
than silently treating a missing signal as "zero risk" or shrinking the
maximum possible score. Hard overrides (a HIGH-severity EXACT blacklist
hit, a multi-identity cluster, or a HIGH-severity front/back cross-check
failure) force HIGH_RISK/MANUAL_REVIEW regardless of the weighted score —
these are the cases a checkpoint cannot afford to average away.
"""
from app.services.deepfake.base import DeepfakeResult
from app.services.face.base import FaceMatchResult
from app.services.identity_graph.base import IdentityGraphResult
from app.services.liveness.base import LivenessResult
from app.services.registry.base import RegistryLookupResult
from app.services.risk.base import RiskEngine, RiskResult, RiskSignalBreakdown
from app.services.tampering.base import TamperingResult
from app.services.validation.base import ValidationResult

_WEIGHTS = {
    "checksum": 0.18,
    "forensics": 0.18,
    "deepfake": 0.12,
    "blacklist": 0.18,
    "face_match": 0.14,
    "identity_graph": 0.08,
    "liveness": 0.12,
}
_FUZZY_CONFIDENCE_MULTIPLIER = 0.5
_LOW_RISK_CEILING = 30
_MEDIUM_RISK_CEILING = 70


def _severity_risk(severity: str) -> float:
    return {"LOW": 0.3, "MEDIUM": 0.6, "HIGH": 1.0}.get(severity.upper(), 0.6)


def _checksum_risk(result: ValidationResult) -> tuple[float, str, dict | None]:
    failed = [f for f in result.findings if f.status == "FAIL"]
    if not failed:
        return 0.0, "all validation checks passed", None
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
    return max(0.0, 1.0 - result.confidence), result.reason, result.location


def _identity_graph_risk(result: IdentityGraphResult) -> tuple[float, str, dict | None]:
    risk = 1.0 if result.status == "CLUSTER_FOUND" else 0.0
    return risk, result.reason, None


def _liveness_risk(result: LivenessResult) -> tuple[float, str, dict | None]:
    return result.score or 0.0, result.reason, None


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
            registry_result, identity_graph_result, validation_result
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
        decision = "CLEAR" if level == "LOW_RISK" else "MANUAL_REVIEW"
        top = breakdown[0]
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
    ) -> tuple[str | None, str | None, str | None]:
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
                if finding.status == "FAIL" and finding.severity == "HIGH" and finding.check.startswith("cross_check"):
                    return (
                        "HIGH_RISK",
                        "MANUAL_REVIEW",
                        f"hard override: severe front/back mismatch — {finding.reason}",
                    )
        return None, None, None
