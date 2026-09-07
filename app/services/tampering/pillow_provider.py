from app.services.tampering.base import TamperingFinding, TamperingProvider, TamperingResult
from app.services.tampering.ela import block_statistics, compute_ela_image, most_anomalous_block

# Heuristic scaling for a block's ELA z-score -> a 0..1 risk contribution.
# Not a trained/calibrated threshold — a hackathon-scale heuristic, documented
# as such rather than presented as a validated forensic model.
_Z_SCORE_RISK_CAP = 8.0


class ELATamperingProvider(TamperingProvider):
    """Baseline forensics via Error Level Analysis. Flags the single
    most-anomalous grid cell in the image as a bounding box, with the
    real block statistics behind the flag — not a hardcoded pass."""

    def __init__(self, jpeg_quality: int = 90, grid: int = 8):
        self._jpeg_quality = jpeg_quality
        self._grid = grid

    def analyze(self, image_bytes: bytes) -> TamperingResult:
        ela_image = compute_ela_image(image_bytes, quality=self._jpeg_quality)
        blocks = block_statistics(ela_image, grid=self._grid)
        worst = most_anomalous_block(blocks)

        risk = max(0.0, min(1.0, worst.z_score / _Z_SCORE_RISK_CAP))
        finding = TamperingFinding(
            type="ela_compression_anomaly",
            confidence=round(risk, 4),
            reason=(
                f"grid cell ({worst.x0},{worst.y0})-({worst.x1},{worst.y1}) has mean "
                f"ELA intensity {worst.mean_error:.2f}, z-score {worst.z_score:.2f} "
                f"against the image's other {len(blocks) - 1} cells"
            ),
            location={"x0": worst.x0, "y0": worst.y0, "x1": worst.x1, "y1": worst.y1},
        )
        return TamperingResult(tampering_risk=round(risk, 4), findings=[finding])
