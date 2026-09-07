from app.services.deepfake.base import DeepfakeProvider, DeepfakeResult
from app.services.deepfake.heuristic import compute_stats

# Heuristic scaling constants — hand-picked for a hackathon-scale signal,
# not calibrated against a labeled deepfake dataset. Documented as such
# rather than presented as validated detection accuracy (same posture as
# _Z_SCORE_RISK_CAP in app/services/tampering/pillow_provider.py).
_FREQUENCY_SPIKE_CAP = 3.0
_NOISE_CV_REFERENCE = 1.5


class HeuristicDeepfakeProvider(DeepfakeProvider):
    """Combines frequency-domain periodicity (upsampling-artifact
    detection) and noise-residual uniformity (over-smoothing detection)
    into one heuristic risk score. Real, computed from the actual image
    bytes every call — not a trained neural network, and not a fixed
    value. See heuristic.py's module docstring for the full rationale."""

    def analyze(self, image_bytes: bytes) -> DeepfakeResult:
        stats = compute_stats(image_bytes)

        freq_risk = max(0.0, min(1.0, stats.frequency_spikiness / _FREQUENCY_SPIKE_CAP))
        noise_risk = max(0.0, min(1.0, 1.0 - (stats.noise_uniformity_cv / _NOISE_CV_REFERENCE)))
        risk = round(0.5 * freq_risk + 0.5 * noise_risk, 4)

        verdict = "no strong indicator of synthetic generation" if risk < 0.5 else "possible synthetic-generation indicators"
        reason = (
            f"frequency-domain spikiness {stats.frequency_spikiness:.2f} (cap {_FREQUENCY_SPIKE_CAP}), "
            f"noise-uniformity CV {stats.noise_uniformity_cv:.2f} (natural-noise reference {_NOISE_CV_REFERENCE}): "
            f"combined heuristic risk {risk:.2f} — {verdict}. Heuristic signal, not a trained classifier."
        )
        return DeepfakeResult(status="ANALYZED", score=risk, reason=reason)
