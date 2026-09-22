"""Block-wise noise inconsistency analysis for document forensics.

Authentic images have relatively uniform sensor noise across their surface.
Manipulated regions (pasted photos, digitally altered text, inserted stamps)
often have a different noise signature — either cleaner (rendered/generated
content) or noisier (recompressed patch) than their surroundings.

This module:
1. Extracts high-frequency noise residual via a high-pass filter
2. Divides the residual into a grid of blocks
3. Computes per-block noise statistics (variance, kurtosis)
4. Flags blocks whose noise deviates significantly from the document median

Pure numpy + OpenCV — no ML models, no external services.
"""
import io
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image


@dataclass
class NoiseBlock:
    x0: int
    y0: int
    x1: int
    y1: int
    noise_variance: float
    noise_mean: float
    z_score: float = 0.0
    kurtosis: float = 0.0


@dataclass
class NoiseFinding:
    finding_type: str
    severity: str
    confidence: float
    description: str
    location: Dict
    evidence: Dict


def analyze_noise_inconsistency(
    image_bytes: bytes,
    grid_size: int = 12,
    z_threshold: float = 2.5,
) -> List[NoiseFinding]:
    """Analyze block-wise noise variance for inconsistencies.

    Returns findings for regions whose noise profile deviates from
    the document's overall noise pattern.
    """
    findings: List[NoiseFinding] = []

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img, dtype=np.float32)

        # Extract noise residual from each channel
        noise_residual = _extract_noise_residual(arr)

        # Compute block-wise statistics
        blocks = _compute_block_stats(noise_residual, grid_size)
        if len(blocks) < 4:
            return findings

        # Find anomalous blocks
        variances = [b.noise_variance for b in blocks]
        median_var = float(np.median(variances))
        mad = float(np.median([abs(v - median_var) for v in variances]))
        robust_std = max(mad * 1.4826, 1e-6)  # MAD to std conversion

        for block in blocks:
            block.z_score = (block.noise_variance - median_var) / robust_std

        # Flag high-variance blocks (noisier than surroundings — recompressed)
        high_noise = [b for b in blocks if b.z_score > z_threshold]
        for block in high_noise:
            confidence = min(1.0, abs(block.z_score) / 6.0)
            severity = "HIGH" if abs(block.z_score) > 5.0 else "MEDIUM" if abs(block.z_score) > 3.5 else "LOW"
            findings.append(NoiseFinding(
                finding_type="noise_high_variance",
                severity=severity,
                confidence=confidence,
                description=f"Region has significantly higher noise than document average (z={block.z_score:.2f}) — possible recompression or digital insertion",
                location={"x0": block.x0, "y0": block.y0, "x1": block.x1, "y1": block.y1},
                evidence={
                    "noise_variance": round(block.noise_variance, 4),
                    "median_variance": round(median_var, 4),
                    "z_score": round(block.z_score, 2),
                    "anomaly_type": "high_noise"
                }
            ))

        # Flag low-variance blocks (cleaner than surroundings — synthetic/generated)
        low_noise = [b for b in blocks if b.z_score < -z_threshold]
        for block in low_noise:
            confidence = min(1.0, abs(block.z_score) / 6.0)
            severity = "HIGH" if abs(block.z_score) > 5.0 else "MEDIUM" if abs(block.z_score) > 3.5 else "LOW"
            findings.append(NoiseFinding(
                finding_type="noise_low_variance",
                severity=severity,
                confidence=confidence,
                description=f"Region has significantly lower noise than document average (z={block.z_score:.2f}) — possible digitally generated or heavily filtered content",
                location={"x0": block.x0, "y0": block.y0, "x1": block.x1, "y1": block.y1},
                evidence={
                    "noise_variance": round(block.noise_variance, 4),
                    "median_variance": round(median_var, 4),
                    "z_score": round(block.z_score, 2),
                    "anomaly_type": "low_noise"
                }
            ))

        # Cross-channel noise correlation check
        channel_findings = _check_channel_noise_correlation(arr, grid_size)
        findings.extend(channel_findings)

    except Exception:
        pass

    return findings


def _extract_noise_residual(img_array: np.ndarray) -> np.ndarray:
    """Extract high-frequency noise residual using a median-filter approach.

    noise = original - denoised(original)
    The residual captures sensor noise and compression artifacts while
    removing image content.
    """
    gray = cv2.cvtColor(img_array.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)

    # Median filter removes noise while preserving edges
    denoised = cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float32)

    # Noise residual
    residual = gray - denoised
    return residual


def _compute_block_stats(
    noise_residual: np.ndarray,
    grid_size: int,
) -> List[NoiseBlock]:
    """Compute per-block noise statistics."""
    h, w = noise_residual.shape
    cell_h = max(1, h // grid_size)
    cell_w = max(1, w // grid_size)

    blocks: List[NoiseBlock] = []
    for row in range(grid_size):
        for col in range(grid_size):
            y0 = row * cell_h
            x0 = col * cell_w
            y1 = h if row == grid_size - 1 else y0 + cell_h
            x1 = w if col == grid_size - 1 else x0 + cell_w

            region = noise_residual[y0:y1, x0:x1]
            if region.size < 4:
                continue

            variance = float(np.var(region))
            mean = float(np.mean(np.abs(region)))

            # Kurtosis measures tail heaviness — manipulated regions often
            # have different kurtosis than authentic sensor noise
            std = float(np.std(region))
            if std > 1e-6:
                kurtosis = float(np.mean(((region - np.mean(region)) / std) ** 4) - 3.0)
            else:
                kurtosis = 0.0

            blocks.append(NoiseBlock(
                x0=int(x0), y0=int(y0), x1=int(x1), y1=int(y1),
                noise_variance=variance,
                noise_mean=mean,
                kurtosis=kurtosis,
            ))

    return blocks


def _check_channel_noise_correlation(
    img_array: np.ndarray,
    grid_size: int,
) -> List[NoiseFinding]:
    """Check cross-channel noise correlation.

    In authentic camera images, R/G/B channels share correlated sensor noise.
    Manipulated regions often break this correlation because the pasted content
    was captured/rendered with a different noise profile.
    """
    findings = []

    try:
        h, w, _ = img_array.shape
        cell_h = max(1, h // grid_size)
        cell_w = max(1, w // grid_size)

        correlations = []

        for row in range(grid_size):
            for col in range(grid_size):
                y0 = row * cell_h
                x0 = col * cell_w
                y1 = min(h, y0 + cell_h)
                x1 = min(w, x0 + cell_w)

                region = img_array[y0:y1, x0:x1]
                if region.shape[0] < 4 or region.shape[1] < 4:
                    continue

                # Extract noise per channel
                r_noise = region[:, :, 0] - cv2.medianBlur(region[:, :, 0].astype(np.uint8), 3).astype(np.float32)
                g_noise = region[:, :, 1] - cv2.medianBlur(region[:, :, 1].astype(np.uint8), 3).astype(np.float32)

                r_flat = r_noise.flatten()
                g_flat = g_noise.flatten()

                if np.std(r_flat) > 1e-6 and np.std(g_flat) > 1e-6:
                    corr = float(np.corrcoef(r_flat, g_flat)[0, 1])
                    correlations.append((corr, x0, y0, x1, y1))

        if len(correlations) < 4:
            return findings

        corr_values = [c[0] for c in correlations]
        median_corr = float(np.median(corr_values))
        mad_corr = float(np.median([abs(c - median_corr) for c in corr_values]))
        std_corr = max(mad_corr * 1.4826, 1e-6)

        for corr, x0, y0, x1, y1 in correlations:
            z = (corr - median_corr) / std_corr
            if abs(z) > 3.0:
                confidence = min(1.0, abs(z) / 6.0)
                findings.append(NoiseFinding(
                    finding_type="channel_correlation_anomaly",
                    severity="MEDIUM" if abs(z) > 4.0 else "LOW",
                    confidence=confidence,
                    description=f"Cross-channel noise correlation anomaly (z={z:.2f}) — region may have been edited with different noise characteristics",
                    location={"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    evidence={
                        "correlation": round(corr, 4),
                        "median_correlation": round(median_corr, 4),
                        "z_score": round(z, 2),
                    }
                ))

    except Exception:
        pass

    return findings
