from app.services.liveness.base import LivenessProvider, LivenessResult
from app.services.liveness.heuristic import compute_stats

# Hand-picked hackathon-scale constants, not calibrated against a labeled
# live/spoof dataset — same posture as the deepfake and ELA heuristics.
_AXIS_RATIO_CAP = 0.4
_SHARPNESS_REFERENCE = 100.0


class HeuristicLivenessProvider(LivenessProvider):
    """Single-image anti-spoofing: axis-aligned frequency energy (screen/
    print grid detection) plus local sharpness (print/out-of-focus-replay
    detection). Real, computed from the actual live-capture bytes every
    call. See base.py for this check's honest scope — it does not verify
    the on-screen challenge was followed, only that the live capture
    doesn't look like a rephotographed print or screen."""

    def analyze(self, live_capture_bytes: bytes) -> LivenessResult:
        stats = compute_stats(live_capture_bytes)

        axis_risk = max(0.0, min(1.0, stats.axis_energy_ratio / _AXIS_RATIO_CAP))
        blur_risk = max(0.0, min(1.0, 1.0 - (stats.sharpness / _SHARPNESS_REFERENCE)))
        risk = round(0.5 * axis_risk + 0.5 * blur_risk, 4)
        status = "LIVE" if risk < 0.5 else "SUSPECTED_SPOOF"

        reason = (
            f"axis-aligned frequency energy ratio {stats.axis_energy_ratio:.2f} (cap {_AXIS_RATIO_CAP}), "
            f"sharpness {stats.sharpness:.1f} (natural reference {_SHARPNESS_REFERENCE}): "
            f"spoof-risk heuristic {risk:.2f} — {status.replace('_', ' ').lower()}. "
            f"Checks for a rephotographed print/screen only; does not verify the on-screen "
            f"challenge prompt was followed — the officer judges that visually."
        )
        return LivenessResult(status=status, score=risk, reason=reason)
