"""Real, self-contained single-image anti-spoofing heuristic for the live
capture: combines an axis-aligned frequency-energy check (screen pixel
grids and print halftone patterns concentrate energy on the horizontal/
vertical frequency axes in a way natural face photos don't) with a local
sharpness check (a rephotographed print or an out-of-focus screen replay
tends to lack the fine high-frequency detail — skin pores, eyelashes,
individual hair strands — a real close-up camera capture has).

Both are heuristic, not calibrated against a labeled spoof/live dataset —
documented as such. See app/services/liveness/base.py for this check's
honest scope (single-image spoof indicators, not challenge-motion
verification).
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass
class LivenessHeuristicStats:
    axis_energy_ratio: float  # fraction of mid/high-freq energy concentrated on-axis
    sharpness: float  # variance of Laplacian — higher = more fine detail


def _to_grayscale_array(image_bytes: bytes, max_dim: int = 512) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    if max(image.size) > max_dim:
        scale = max_dim / max(image.size)
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    return np.asarray(image, dtype=np.float64)


def _axis_energy_ratio(gray: np.ndarray, axis_band_px: int = 3) -> float:
    """Fraction of mid/high-frequency spectral energy that sits within a
    thin band straddling the horizontal/vertical frequency axes, versus
    total mid/high-frequency energy. A real photo's texture is not
    aligned to the pixel grid; a rephotographed screen/print often is."""
    h, w = gray.shape
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
    cy, cx = h // 2, w // 2

    # Exclude the low-frequency DC-dominated core (real image content lives here).
    y, x = np.ogrid[:h, :w]
    radius = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    min_radius = min(cy, cx) * 0.15
    mid_high_mask = radius > min_radius

    total_energy = float(spectrum[mid_high_mask].sum())
    if total_energy <= 1e-9:
        return 0.0

    axis_mask = np.zeros_like(spectrum, dtype=bool)
    axis_mask[max(0, cy - axis_band_px) : cy + axis_band_px, :] = True
    axis_mask[:, max(0, cx - axis_band_px) : cx + axis_band_px] = True
    axis_mask &= mid_high_mask

    axis_energy = float(spectrum[axis_mask].sum())
    return axis_energy / total_energy


def _sharpness(gray: np.ndarray) -> float:
    """Variance of the discrete Laplacian — a standard focus/detail
    measure. Low values indicate a flat, blurry, or low-detail source
    (consistent with a print or an out-of-focus screen recapture)."""
    kernel_result = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1]
        + gray[2:, 1:-1]
        + gray[1:-1, :-2]
        + gray[1:-1, 2:]
    )
    return float(kernel_result.var())


def compute_stats(image_bytes: bytes) -> LivenessHeuristicStats:
    gray = _to_grayscale_array(image_bytes)
    return LivenessHeuristicStats(
        axis_energy_ratio=_axis_energy_ratio(gray),
        sharpness=_sharpness(gray),
    )
