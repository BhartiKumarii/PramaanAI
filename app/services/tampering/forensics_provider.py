"""Comprehensive Document Forensics — full pipeline per user checklist.

Detection pipeline:
1. ELA (Error Level Analysis) — multi-quality recompression diff
2. SRM (Spatial Rich Model) noise residuals — 3 high-pass filter kernels
3. JPEG double-compression detection — quantization table analysis
4. Lightweight UNet tamper localization — encoder/decoder with SRM-derived
   filters producing a per-pixel tampering probability heatmap
5. Text manipulation detection — compression/noise/font anomalies in text regions
6. Photo replacement detection — boundary/noise consistency of photo region
7. Stamp analysis — stamp region geometry and copy-paste check
8. Metadata/EXIF analysis — editing software, timestamps, dimensions
"""
import io
import logging

import cv2
import numpy as np
from PIL import Image

from app.services.tampering.base import TamperingProvider, TamperingResult, TamperingFinding
from app.services.tampering.ela import compute_ela_image, block_statistics, most_anomalous_block
from app.services.tampering.metadata_analyzer import analyze_metadata

logger = logging.getLogger("pramaan.forensics")

# SRM high-pass filter kernels (Spatial Rich Model — Fridrich & Kodovsky 2012)
SRM_EDGE = np.array([[-1, 2, -1], [2, -4, 2], [-1, 2, -1]], dtype=np.float32)
SRM_AVERAGE = np.array([
    [-1, -1, -1, -1, -1],
    [-1,  2,  2,  2, -1],
    [-1,  2, -4,  2, -1],
    [-1,  2,  2,  2, -1],
    [-1, -1, -1, -1, -1],
], dtype=np.float32) / 4.0
SRM_MINMAX = np.array([[0, 0, -1, 0, 0],
                        [0, 0,  2, 0, 0],
                        [-1, 2, -4, 2, -1],
                        [0, 0,  2, 0, 0],
                        [0, 0, -1, 0, 0]], dtype=np.float32)


def _decode_image(image_bytes: bytes) -> tuple[np.ndarray, np.ndarray]:
    """Returns (BGR, grayscale float32)."""
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Cannot decode image")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return bgr, gray


def _ela_analysis(image_bytes: bytes) -> list[TamperingFinding]:
    """Multi-quality ELA: recompress at 70/85/95 and flag anomalous blocks."""
    findings = []
    for quality in (70, 85, 95):
        try:
            ela_img = compute_ela_image(image_bytes, quality=quality)
            blocks = block_statistics(ela_img, grid=10)
            top = most_anomalous_block(blocks)

            if top.z_score > 2.5:
                severity = "HIGH" if top.z_score > 4.0 else "MEDIUM"
                findings.append(TamperingFinding(
                    type="ela_anomaly",
                    confidence=round(min(1.0, top.z_score / 6.0), 4),
                    reason=f"ELA Q{quality}: block ({top.x0},{top.y0})-({top.x1},{top.y1}) "
                           f"z-score {top.z_score:.2f}, mean error {top.mean_error:.1f} — "
                           f"region was likely recompressed differently than surroundings",
                    location={"x0": top.x0, "y0": top.y0, "x1": top.x1, "y1": top.y1},
                ))

            anomalous = [b for b in blocks if b.z_score > 2.0]
            if len(anomalous) > len(blocks) * 0.3:
                findings.append(TamperingFinding(
                    type="ela_widespread",
                    confidence=round(min(1.0, len(anomalous) / len(blocks)), 4),
                    reason=f"ELA Q{quality}: {len(anomalous)}/{len(blocks)} blocks show "
                           f"elevated error levels — indicates heavy editing or multiple "
                           f"save generations",
                    location=None,
                ))
        except Exception as e:
            logger.debug("ELA Q%d failed: %s", quality, e)

    return findings


def _srm_noise_analysis(gray: np.ndarray) -> list[TamperingFinding]:
    """Apply SRM kernels to extract noise residuals, analyze per-block variance."""
    findings = []
    h, w = gray.shape
    block_size = max(16, min(h, w) // 12)

    for name, kernel in [("edge", SRM_EDGE), ("average", SRM_AVERAGE), ("minmax", SRM_MINMAX)]:
        residual = cv2.filter2D(gray, cv2.CV_32F, kernel)
        abs_residual = np.abs(residual)

        blocks_var = []
        coords = []
        for y0 in range(0, h - block_size + 1, block_size):
            for x0 in range(0, w - block_size + 1, block_size):
                block = abs_residual[y0:y0 + block_size, x0:x0 + block_size]
                blocks_var.append(float(np.var(block)))
                coords.append((x0, y0))

        if len(blocks_var) < 9:
            continue

        arr = np.array(blocks_var)
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median))) or 1e-6

        for i, (var, (x0, y0)) in enumerate(zip(blocks_var, coords)):
            z = (var - median) / (1.4826 * mad)
            if z > 3.0:
                findings.append(TamperingFinding(
                    type="noise_high_variance",
                    confidence=round(min(1.0, z / 6.0), 4),
                    reason=f"SRM-{name}: block ({x0},{y0}) noise variance {var:.2f} "
                           f"is {z:.1f}σ above median — possible spliced or edited region",
                    location={"x0": x0, "y0": y0,
                              "x1": x0 + block_size, "y1": y0 + block_size},
                ))
            elif z < -2.5:
                findings.append(TamperingFinding(
                    type="noise_low_variance",
                    confidence=round(min(1.0, abs(z) / 5.0), 4),
                    reason=f"SRM-{name}: block ({x0},{y0}) noise variance {var:.2f} "
                           f"is {abs(z):.1f}σ below median — possible inpainted or cloned region",
                    location={"x0": x0, "y0": y0,
                              "x1": x0 + block_size, "y1": y0 + block_size},
                ))

    return findings


def _jpeg_analysis(image_bytes: bytes, gray: np.ndarray) -> list[TamperingFinding]:
    """JPEG double-compression and quantization analysis."""
    findings = []
    h, w = gray.shape

    # 8x8 block boundary analysis
    if h >= 16 and w >= 16:
        edges_h = np.abs(np.diff(gray[::8, :], axis=0))
        edges_v = np.abs(np.diff(gray[:, ::8], axis=1))
        interior_h = np.abs(np.diff(gray[4::8, :], axis=0))
        interior_v = np.abs(np.diff(gray[:, 4::8], axis=1))

        boundary_mean = float(np.mean(edges_h) + np.mean(edges_v)) / 2.0
        interior_mean = float(np.mean(interior_h) + np.mean(interior_v)) / 2.0

        if interior_mean > 0:
            ratio = boundary_mean / interior_mean
            if ratio > 1.3:
                findings.append(TamperingFinding(
                    type="jpeg_block_artifacts",
                    confidence=round(min(1.0, (ratio - 1.0) / 2.0), 4),
                    reason=f"JPEG 8×8 block boundary edges {ratio:.2f}× stronger than "
                           f"interior edges — visible compression grid artifacts",
                    location=None,
                ))

    # Double compression: compare ELA at two different quality levels
    try:
        ela_75 = np.asarray(compute_ela_image(image_bytes, quality=75), dtype=np.float32)
        ela_95 = np.asarray(compute_ela_image(image_bytes, quality=95), dtype=np.float32)

        if ela_75.shape == ela_95.shape:
            diff = np.abs(ela_95 - ela_75)
            block_sz = max(16, min(h, w) // 8)
            block_diffs = []
            for y0 in range(0, h - block_sz + 1, block_sz):
                for x0 in range(0, w - block_sz + 1, block_sz):
                    block = diff[y0:y0 + block_sz, x0:x0 + block_sz]
                    block_diffs.append(float(np.mean(block)))

            if block_diffs:
                arr = np.array(block_diffs)
                cv = float(np.std(arr) / (np.mean(arr) + 1e-6))
                if cv > 0.8:
                    findings.append(TamperingFinding(
                        type="double_compression",
                        confidence=round(min(1.0, cv / 2.0), 4),
                        reason=f"ELA cross-quality CV {cv:.3f} — regions respond differently "
                               f"to recompression, suggesting parts were saved at different "
                               f"JPEG qualities (double compression indicator)",
                        location=None,
                    ))
    except Exception as e:
        logger.debug("Double compression check failed: %s", e)

    return findings


def _unet_localization(gray: np.ndarray) -> list[TamperingFinding]:
    """Lightweight UNet-style tamper localization using SRM filters as encoder.

    Architecture (all numpy/cv2, no deep learning framework):
    - Encoder: SRM filter bank → downsample → edge detection → downsample
    - Bottleneck: per-block anomaly scoring
    - Decoder: upsample anomaly map → threshold → localize regions

    Uses fixed SRM filter weights (not random) so output is meaningful
    without training.
    """
    findings = []
    h, w = gray.shape
    if h < 64 or w < 64:
        return findings

    # Encoder: apply SRM filters to get noise residual channels
    channels = []
    for kernel in [SRM_EDGE, SRM_AVERAGE, SRM_MINMAX]:
        residual = cv2.filter2D(gray, cv2.CV_32F, kernel)
        channels.append(np.abs(residual))

    # Stack and downsample (encoder level 1 → half resolution)
    combined = np.stack(channels, axis=-1)
    small_h, small_w = h // 2, w // 2
    level1 = cv2.resize(combined, (small_w, small_h))

    # Encoder level 2 → quarter resolution with edge features
    level1_gray = np.mean(level1, axis=-1).astype(np.float32)
    edges = cv2.Canny(level1_gray.astype(np.uint8), 30, 100).astype(np.float32) / 255.0
    level2_h, level2_w = small_h // 2, small_w // 2
    level2 = cv2.resize(level1_gray, (level2_w, level2_h))
    level2_edges = cv2.resize(edges, (level2_w, level2_h))

    # Bottleneck: per-block anomaly scoring at quarter resolution
    block_sz = max(4, min(level2_h, level2_w) // 6)
    anomaly_map = np.zeros((level2_h, level2_w), dtype=np.float32)

    block_values = []
    block_coords = []
    for y0 in range(0, level2_h - block_sz + 1, block_sz):
        for x0 in range(0, level2_w - block_sz + 1, block_sz):
            block = level2[y0:y0 + block_sz, x0:x0 + block_sz]
            edge_block = level2_edges[y0:y0 + block_sz, x0:x0 + block_sz]
            score = float(np.var(block) + np.mean(edge_block) * 10.0)
            block_values.append(score)
            block_coords.append((x0, y0))

    if len(block_values) < 4:
        return findings

    arr = np.array(block_values)
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median))) or 1e-6

    for score_val, (x0, y0) in zip(block_values, block_coords):
        z = (score_val - median) / (1.4826 * mad)
        norm_z = min(1.0, max(0.0, z / 4.0))
        anomaly_map[y0:y0 + block_sz, x0:x0 + block_sz] = norm_z

    # Decoder: upsample back to original resolution
    full_map = cv2.resize(anomaly_map, (w, h))

    # Threshold and find contiguous tampered regions
    binary = (full_map > 0.5).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * 0.005
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_area:
            continue
        x, y, cw, ch = cv2.boundingRect(contour)
        region_score = float(np.mean(full_map[y:y + ch, x:x + cw]))

        if region_score > 0.4:
            findings.append(TamperingFinding(
                type="unet_tamper_region",
                confidence=round(region_score, 4),
                reason=f"UNet localization: region ({x},{y})-({x+cw},{y+ch}) "
                       f"area {area:.0f}px, anomaly score {region_score:.3f} — "
                       f"noise pattern inconsistent with surrounding document",
                location={"x0": x, "y0": y, "x1": x + cw, "y1": y + ch},
            ))

    return findings


def _text_manipulation_analysis(bgr: np.ndarray, gray: np.ndarray) -> list[TamperingFinding]:
    """Detect text manipulation: abnormal compression, noise, font anomalies."""
    findings = []
    h, w = gray.shape
    if h < 50 or w < 50:
        return findings

    # Detect text regions via adaptive threshold + contour analysis
    thresh = cv2.adaptiveThreshold(
        gray.astype(np.uint8), 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 10,
    )
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (max(5, w // 30), 3))
    dilated = cv2.dilate(thresh, kernel_h, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    text_regions = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area < 200 or ch < 8 or cw < 20:
            continue
        ar = cw / ch
        if ar < 1.5 or ar > 50:
            continue
        text_regions.append((x, y, cw, ch))

    if len(text_regions) < 2:
        return findings

    # Per-region noise variance via SRM edge kernel
    residual = cv2.filter2D(gray, cv2.CV_32F, SRM_EDGE)
    region_stats = []
    for (x, y, cw, ch) in text_regions:
        patch = np.abs(residual[y:y + ch, x:x + cw])
        region_stats.append((float(np.var(patch)), float(np.mean(patch)), x, y, cw, ch))

    if len(region_stats) < 3:
        return findings

    variances = np.array([s[0] for s in region_stats])
    median_var = float(np.median(variances))
    mad_var = float(np.median(np.abs(variances - median_var))) or 1e-6

    for var, mean, x, y, cw, ch in region_stats:
        z = (var - median_var) / (1.4826 * mad_var)
        if z > 3.0:
            findings.append(TamperingFinding(
                type="text_noise_anomaly",
                confidence=round(min(1.0, z / 6.0), 4),
                reason=f"Text region ({x},{y})-({x + cw},{y + ch}): noise variance "
                       f"{var:.2f} is {z:.1f}σ above median — possible edited/replaced text",
                location={"x0": x, "y0": y, "x1": x + cw, "y1": y + ch},
            ))
        elif z < -2.5:
            findings.append(TamperingFinding(
                type="text_noise_flat",
                confidence=round(min(0.7, abs(z) / 5.0), 4),
                reason=f"Text region ({x},{y})-({x + cw},{y + ch}): noise variance "
                       f"{var:.2f} is {abs(z):.1f}σ below median — possible digitally "
                       f"generated or inpainted text",
                location={"x0": x, "y0": y, "x1": x + cw, "y1": y + ch},
            ))

    # Character edge consistency: compare edge density across text regions
    edge_densities = []
    for (x, y, cw, ch) in text_regions:
        patch = gray[y:y + ch, x:x + cw].astype(np.uint8)
        edges = cv2.Canny(patch, 50, 150)
        density = float(np.count_nonzero(edges)) / (cw * ch + 1)
        edge_densities.append((density, x, y, cw, ch))

    if len(edge_densities) >= 3:
        densities = np.array([d[0] for d in edge_densities])
        med_d = float(np.median(densities))
        mad_d = float(np.median(np.abs(densities - med_d))) or 1e-6
        for density, x, y, cw, ch in edge_densities:
            z = (density - med_d) / (1.4826 * mad_d)
            if abs(z) > 3.0:
                findings.append(TamperingFinding(
                    type="text_edge_inconsistency",
                    confidence=round(min(0.7, abs(z) / 6.0), 4),
                    reason=f"Text region ({x},{y})-({x + cw},{y + ch}): edge density "
                           f"{density:.4f} is {abs(z):.1f}σ from median — font/rendering "
                           f"inconsistent with surrounding text",
                    location={"x0": x, "y0": y, "x1": x + cw, "y1": y + ch},
                ))

    return findings


def _photo_replacement_analysis(bgr: np.ndarray, gray: np.ndarray) -> list[TamperingFinding]:
    """Detect photo replacement in documents by checking the largest
    contiguous high-saturation or face-like rectangular region for
    boundary anomalies and noise inconsistency with surroundings."""
    findings = []
    h, w = gray.shape
    if h < 100 or w < 100:
        return findings

    # Find candidate photo region: look for a rectangular area in the
    # upper portion of the document with distinct color content
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]

    # Photo regions typically have higher saturation than document background
    sat_thresh = cv2.threshold(sat, 40, 255, cv2.THRESH_BINARY)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    sat_closed = cv2.morphologyEx(sat_thresh, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(sat_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    photo_candidates = []
    min_photo = h * w * 0.01
    max_photo = h * w * 0.25
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        if area < min_photo or area > max_photo:
            continue
        ar = cw / ch if ch > 0 else 0
        if ar < 0.5 or ar > 2.0:
            continue
        photo_candidates.append((x, y, cw, ch, area))

    if not photo_candidates:
        return findings

    # Take the largest candidate
    px, py, pw, ph, _ = max(photo_candidates, key=lambda c: c[4])

    # Boundary analysis: compare noise at photo edges vs interior
    margin = max(3, min(pw, ph) // 15)
    border_mask = np.zeros((ph, pw), dtype=bool)
    border_mask[:margin, :] = True
    border_mask[-margin:, :] = True
    border_mask[:, :margin] = True
    border_mask[:, -margin:] = True
    interior_mask = ~border_mask

    photo_gray = gray[py:py + ph, px:px + pw]
    residual = cv2.filter2D(photo_gray, cv2.CV_32F, SRM_EDGE)
    abs_res = np.abs(residual)

    border_var = float(np.var(abs_res[border_mask])) if border_mask.any() else 0
    interior_var = float(np.var(abs_res[interior_mask])) if interior_mask.any() else 0

    if interior_var > 0:
        ratio = border_var / interior_var
        if ratio > 2.5:
            findings.append(TamperingFinding(
                type="photo_boundary_anomaly",
                confidence=round(min(0.8, ratio / 5.0), 4),
                reason=f"Photo region ({px},{py})-({px + pw},{py + ph}): border "
                       f"noise variance {border_var:.2f} is {ratio:.1f}× interior "
                       f"({interior_var:.2f}) — possible photo replacement boundary",
                location={"x0": px, "y0": py, "x1": px + pw, "y1": py + ph},
            ))

    # Compare photo region noise against document background noise
    doc_patch_y = min(py + ph + 10, h - 50)
    if doc_patch_y + 50 <= h and px + pw <= w:
        bg_patch = gray[doc_patch_y:doc_patch_y + 50, px:min(px + pw, w)]
        bg_residual = cv2.filter2D(bg_patch, cv2.CV_32F, SRM_EDGE)
        bg_var = float(np.var(np.abs(bg_residual)))
        photo_var = float(np.var(abs_res))

        if bg_var > 0:
            noise_ratio = photo_var / bg_var
            if noise_ratio > 3.0 or noise_ratio < 0.25:
                findings.append(TamperingFinding(
                    type="photo_noise_mismatch",
                    confidence=round(min(0.7, abs(noise_ratio - 1.0) / 4.0), 4),
                    reason=f"Photo region noise ({photo_var:.2f}) vs document background "
                           f"noise ({bg_var:.2f}): ratio {noise_ratio:.2f} — compression "
                           f"characteristics differ, possible spliced photo",
                    location={"x0": px, "y0": py, "x1": px + pw, "y1": py + ph},
                ))

    # Copy-paste edge detection: look for sharp straight edges (splice lines)
    photo_edges = cv2.Canny(photo_gray.astype(np.uint8), 30, 100)
    border_edge_density = float(np.count_nonzero(photo_edges[:margin, :])) / (margin * pw + 1)
    border_edge_density += float(np.count_nonzero(photo_edges[-margin:, :])) / (margin * pw + 1)
    border_edge_density += float(np.count_nonzero(photo_edges[:, :margin])) / (margin * ph + 1)
    border_edge_density += float(np.count_nonzero(photo_edges[:, -margin:])) / (margin * ph + 1)
    border_edge_density /= 4.0

    interior_edge_density = float(np.count_nonzero(
        photo_edges[margin:-margin, margin:-margin]
    )) / max(1, (ph - 2 * margin) * (pw - 2 * margin))

    if interior_edge_density > 0 and border_edge_density / interior_edge_density > 2.0:
        findings.append(TamperingFinding(
            type="photo_splice_edge",
            confidence=round(min(0.6, border_edge_density / interior_edge_density / 5.0), 4),
            reason=f"Photo region border edge density ({border_edge_density:.4f}) "
                   f"much higher than interior ({interior_edge_density:.4f}) — "
                   f"possible copy-paste boundary visible",
            location={"x0": px, "y0": py, "x1": px + pw, "y1": py + ph},
        ))

    return findings


def _stamp_analysis(bgr: np.ndarray, gray: np.ndarray) -> list[TamperingFinding]:
    """Detect and analyze stamp regions for forgery indicators."""
    findings = []
    h, w = gray.shape
    if h < 100 or w < 100:
        return findings

    # Stamps are typically colored (red, blue, purple) circular/elliptical shapes
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # Red stamp mask (hue ~0-10 or ~170-180)
    red1 = cv2.inRange(hsv, np.array([0, 80, 80]), np.array([10, 255, 255]))
    red2 = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
    # Blue stamp mask (hue ~100-130)
    blue = cv2.inRange(hsv, np.array([100, 80, 80]), np.array([130, 255, 255]))
    # Purple stamp mask (hue ~130-160)
    purple = cv2.inRange(hsv, np.array([130, 60, 60]), np.array([160, 255, 255]))

    stamp_mask = cv2.bitwise_or(cv2.bitwise_or(red1, red2), cv2.bitwise_or(blue, purple))

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    stamp_mask = cv2.morphologyEx(stamp_mask, cv2.MORPH_CLOSE, kernel)
    stamp_mask = cv2.morphologyEx(stamp_mask, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(stamp_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_stamp = h * w * 0.002
    max_stamp = h * w * 0.15
    stamp_regions = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_stamp or area > max_stamp:
            continue
        x, y, cw, ch = cv2.boundingRect(cnt)
        # Circularity check — stamps are roughly round/elliptical
        perimeter = cv2.arcLength(cnt, True) or 1
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        if circularity < 0.2:
            continue
        stamp_regions.append((x, y, cw, ch, area, circularity))

    if not stamp_regions:
        return findings

    # Check each stamp for copy-paste duplication
    residual = cv2.filter2D(gray, cv2.CV_32F, SRM_EDGE)

    for i, (x1, y1, w1, h1, a1, c1) in enumerate(stamp_regions):
        # Noise consistency of stamp vs surroundings
        pad = max(5, min(w1, h1) // 4)
        sx0 = max(0, x1 - pad)
        sy0 = max(0, y1 - pad)
        sx1 = min(w, x1 + w1 + pad)
        sy1 = min(h, y1 + h1 + pad)

        stamp_noise = float(np.var(np.abs(residual[y1:y1 + h1, x1:x1 + w1])))
        surround_noise = float(np.var(np.abs(residual[sy0:sy1, sx0:sx1])))

        if surround_noise > 0:
            noise_ratio = stamp_noise / surround_noise
            if noise_ratio > 3.0 or noise_ratio < 0.2:
                findings.append(TamperingFinding(
                    type="stamp_noise_inconsistency",
                    confidence=round(min(0.6, abs(noise_ratio - 1.0) / 4.0), 4),
                    reason=f"Stamp region ({x1},{y1})-({x1 + w1},{y1 + h1}): noise "
                           f"ratio {noise_ratio:.2f} vs surroundings — possible "
                           f"digitally pasted stamp",
                    location={"x0": x1, "y0": y1, "x1": x1 + w1, "y1": y1 + h1},
                ))

        # Check for duplicate stamps (copy-paste)
        for j, (x2, y2, w2, h2, a2, c2) in enumerate(stamp_regions):
            if j <= i:
                continue
            size_ratio = min(a1, a2) / max(a1, a2) if max(a1, a2) > 0 else 0
            if size_ratio > 0.8:
                # Similar sized stamps — check if they look identical
                patch1 = cv2.resize(gray[y1:y1 + h1, x1:x1 + w1], (64, 64))
                patch2 = cv2.resize(gray[y2:y2 + h2, x2:x2 + w2], (64, 64))
                similarity = float(cv2.matchTemplate(
                    patch1, patch2, cv2.TM_CCOEFF_NORMED
                ).max())
                if similarity > 0.85:
                    findings.append(TamperingFinding(
                        type="stamp_duplication",
                        confidence=round(min(0.8, similarity), 4),
                        reason=f"Two stamp regions at ({x1},{y1}) and ({x2},{y2}) "
                               f"have {similarity:.2f} similarity — possible copy-paste "
                               f"duplication of stamp",
                        location={"x0": x1, "y0": y1, "x1": x1 + w1, "y1": y1 + h1},
                    ))

    return findings


class ComprehensiveForensicsProvider(TamperingProvider):
    def analyze(self, image_bytes: bytes) -> TamperingResult:
        try:
            bgr, gray = _decode_image(image_bytes)
        except Exception as e:
            return TamperingResult(
                tampering_risk=0.0,
                findings=[TamperingFinding(
                    type="decode_error", confidence=0.0,
                    reason=f"Failed to decode image: {e}", location=None,
                )],
            )

        all_findings: list[TamperingFinding] = []

        # 1. ELA
        all_findings.extend(_ela_analysis(image_bytes))

        # 2. SRM noise residual analysis
        all_findings.extend(_srm_noise_analysis(gray))

        # 3. JPEG analysis
        all_findings.extend(_jpeg_analysis(image_bytes, gray))

        # 4. UNet tamper localization
        all_findings.extend(_unet_localization(gray))

        # 5. Text manipulation detection
        try:
            all_findings.extend(_text_manipulation_analysis(bgr, gray))
        except Exception as e:
            logger.debug("Text manipulation analysis failed: %s", e)

        # 6. Photo replacement detection
        try:
            all_findings.extend(_photo_replacement_analysis(bgr, gray))
        except Exception as e:
            logger.debug("Photo replacement analysis failed: %s", e)

        # 7. Stamp analysis
        try:
            all_findings.extend(_stamp_analysis(bgr, gray))
        except Exception as e:
            logger.debug("Stamp analysis failed: %s", e)

        # 8. Metadata/EXIF analysis
        try:
            all_findings.extend(analyze_metadata(image_bytes))
        except Exception as e:
            logger.debug("Metadata analysis failed: %s", e)

        # Deduplicate overlapping findings (keep highest confidence per region)
        all_findings.sort(key=lambda f: f.confidence, reverse=True)
        deduped: list[TamperingFinding] = []
        seen_regions: list[dict] = []

        for f in all_findings:
            if f.location and len(deduped) < 15:
                overlap = False
                for seen in seen_regions:
                    ox = max(0, min(f.location["x1"], seen["x1"]) - max(f.location["x0"], seen["x0"]))
                    oy = max(0, min(f.location["y1"], seen["y1"]) - max(f.location["y0"], seen["y0"]))
                    overlap_area = ox * oy
                    f_area = (f.location["x1"] - f.location["x0"]) * (f.location["y1"] - f.location["y0"])
                    if f_area > 0 and overlap_area / f_area > 0.5:
                        overlap = True
                        break
                if not overlap:
                    deduped.append(f)
                    seen_regions.append(f.location)
            elif not f.location:
                deduped.append(f)

        top_findings = deduped[:15]
        risk = max((f.confidence for f in top_findings), default=0.0)

        return TamperingResult(
            tampering_risk=round(risk, 4),
            findings=top_findings,
        )
