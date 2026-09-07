"""Real, self-contained deepfake heuristic: combines a frequency-domain
periodicity check with a noise-uniformity check, both computed from the
actual image pixels via Pillow + numpy.

This is NOT a trained neural classifier — there is no torch/transformers
stack or downloaded model file here (see the module docstring history in
base.py for why: no cmake/heavy-download budget, and no verified source
for a pretrained weights file). It is a genuine, working signal instead
of a fixed value:

1. Frequency periodicity: many GAN generators upsample via transposed
   convolution / pixel-shuffle layers, which leave periodic grid-like
   artifacts in the 2D FFT magnitude spectrum. We measure how "spiky"
   the mid/high-frequency radial energy profile is (coefficient of
   variation) — real camera photos have a smooth falloff; periodic
   upsampling artifacts show sharp peaks.
2. Noise-residual uniformity: real camera sensor noise is
   content-correlated (heteroscedastic — more visible noise in
   high-detail or dark regions, less in flat/bright ones). Many
   AI-generated or heavily denoised images have unnaturally uniform
   noise across the frame. We high-pass filter the image, split it into
   blocks, and measure the coefficient of variation of per-block noise
   variance — lower CV is more suspicious.

Both signals are heuristic, not calibrated against a labeled dataset —
documented as such rather than presented as validated detection accuracy.
"""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter


@dataclass
class DeepfakeHeuristicStats:
    frequency_spikiness: float  # coefficient of variation of radial FFT energy
    noise_uniformity_cv: float  # coefficient of variation of per-block noise variance


def _to_grayscale_array(image_bytes: bytes, max_dim: int = 512) -> np.ndarray:
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    # Downscale for speed — periodicity/noise statistics don't need full resolution.
    if max(image.size) > max_dim:
        scale = max_dim / max(image.size)
        image = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))))
    return np.asarray(image, dtype=np.float64)


def _frequency_spikiness(gray: np.ndarray) -> float:
    """Coefficient of variation of the azimuthally-averaged FFT magnitude
    spectrum in the mid/high-frequency band. Higher = more periodic/spiky
    energy distribution, consistent with upsampling grid artifacts."""
    h, w = gray.shape
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
    cy, cx = h // 2, w // 2
    y, x = np.ogrid[:h, :w]
    radius = np.sqrt((y - cy) ** 2 + (x - cx) ** 2).astype(np.int32)
    max_radius = min(cy, cx)
    if max_radius < 8:
        return 0.0

    radial_mean = np.zeros(max_radius)
    for r in range(max_radius):
        mask = radius == r
        if mask.any():
            radial_mean[r] = spectrum[mask].mean()

    # Mid/high band: skip the low-frequency DC-dominated core.
    band = radial_mean[max_radius // 4 :]
    band = band[band > 0]
    if band.size < 4:
        return 0.0
    mean = float(band.mean())
    if mean <= 0:
        return 0.0
    return float(band.std() / mean)


def _noise_uniformity_cv(gray: np.ndarray, block_size: int = 16) -> float:
    """Coefficient of variation of per-block noise variance, from a
    high-pass (original minus blurred) residual. Lower = suspiciously
    uniform noise across the image."""
    image = Image.fromarray(gray.astype(np.uint8))
    blurred = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=2)), dtype=np.float64)
    residual = gray - blurred

    h, w = residual.shape
    variances = []
    for y0 in range(0, h - block_size + 1, block_size):
        for x0 in range(0, w - block_size + 1, block_size):
            block = residual[y0 : y0 + block_size, x0 : x0 + block_size]
            variances.append(block.var())

    if len(variances) < 4:
        return 1.0  # too small an image to say anything — don't penalize
    variances_arr = np.array(variances)
    mean = float(variances_arr.mean())
    if mean <= 1e-9:
        return 0.0
    return float(variances_arr.std() / mean)


def compute_stats(image_bytes: bytes) -> DeepfakeHeuristicStats:
    gray = _to_grayscale_array(image_bytes)
    return DeepfakeHeuristicStats(
        frequency_spikiness=_frequency_spikiness(gray),
        noise_uniformity_cv=_noise_uniformity_cv(gray),
    )
