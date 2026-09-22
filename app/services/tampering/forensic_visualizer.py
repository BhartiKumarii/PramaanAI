"""Forensic evidence visualization generator.

Creates highlighted images showing suspicious regions for officer review:
1. ELA heatmap — colorized error-level analysis overlay
2. Noise map — block-wise noise variance visualization
3. Annotated findings — bounding boxes over suspicious regions with labels
4. Combined forensic report — all evidence in one image

Generates JPEG bytes that can be stored alongside the verification record
and displayed in the officer's dashboard. Never modifies the original image.
"""
import io
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.tampering.ela import compute_ela_image, block_statistics


SEVERITY_COLORS = {
    "HIGH": (220, 40, 40),      # Red
    "MEDIUM": (240, 180, 30),   # Amber
    "LOW": (60, 160, 240),      # Blue
}

FINDING_COLORS = {
    "compression_anomaly": (255, 100, 50),
    "photo_edge_anomaly": (255, 50, 50),
    "photo_lighting_inconsistency": (255, 80, 80),
    "photo_quality_mismatch": (255, 120, 50),
    "font_inconsistency": (200, 50, 255),
    "character_misalignment": (180, 80, 255),
    "text_background_anomaly": (160, 60, 220),
    "stamp_color_inconsistency": (50, 200, 50),
    "stamp_edge_anomaly": (30, 180, 30),
    "stamp_opacity_anomaly": (80, 220, 80),
    "missing_hologram": (255, 200, 0),
    "watermark_tampering": (255, 220, 50),
    "suspicious_qr_code": (0, 200, 255),
    "noise_high_variance": (255, 150, 0),
    "noise_low_variance": (0, 150, 255),
    "channel_correlation_anomaly": (200, 100, 255),
    "copy_move_detected": (255, 0, 100),
    "editing_software_detected": (255, 50, 50),
}


def generate_ela_heatmap(image_bytes: bytes, quality: int = 90) -> bytes:
    """Generate a colorized ELA heatmap overlaid on the original image.

    Red/yellow = high error (possible manipulation)
    Blue/green = low error (consistent compression)
    """
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        ela = compute_ela_image(image_bytes, quality=quality)

        # Amplify ELA signal for visibility
        ela_array = np.array(ela, dtype=np.float32)
        ela_max = ela_array.max()
        if ela_max > 0:
            ela_normalized = (ela_array / ela_max * 255).astype(np.uint8)
        else:
            ela_normalized = ela_array.astype(np.uint8)

        # Apply colormap (COLORMAP_JET: blue=low, red=high)
        heatmap = cv2.applyColorMap(ela_normalized, cv2.COLORMAP_JET)
        heatmap_rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        heatmap_pil = Image.fromarray(heatmap_rgb).resize(original.size, Image.LANCZOS)

        # Blend with original
        blended = Image.blend(original, heatmap_pil, alpha=0.5)

        # Add label
        draw = ImageDraw.Draw(blended)
        _draw_label(draw, "ELA ANALYSIS — Red=High Error, Blue=Low Error", 10, 10)

        buf = io.BytesIO()
        blended.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    except Exception:
        return b""


def generate_noise_map(image_bytes: bytes, grid_size: int = 16) -> bytes:
    """Generate a block-wise noise variance visualization."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img, dtype=np.float32)

        # Extract noise residual
        gray = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32)
        denoised = cv2.medianBlur(gray.astype(np.uint8), 3).astype(np.float32)
        residual = gray - denoised

        h, w = residual.shape
        cell_h = max(1, h // grid_size)
        cell_w = max(1, w // grid_size)

        # Compute per-block variance
        variance_map = np.zeros((h, w), dtype=np.float32)
        for row in range(grid_size):
            for col in range(grid_size):
                y0 = row * cell_h
                x0 = col * cell_w
                y1 = h if row == grid_size - 1 else y0 + cell_h
                x1 = w if col == grid_size - 1 else x0 + cell_w
                block = residual[y0:y1, x0:x1]
                variance_map[y0:y1, x0:x1] = np.var(block)

        # Normalize and colorize
        v_max = variance_map.max()
        if v_max > 0:
            normalized = (variance_map / v_max * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(variance_map, dtype=np.uint8)

        heatmap = cv2.applyColorMap(normalized, cv2.COLORMAP_HOT)
        heatmap_rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        heatmap_pil = Image.fromarray(heatmap_rgb)

        # Blend
        blended = Image.blend(img, heatmap_pil, alpha=0.45)

        draw = ImageDraw.Draw(blended)
        _draw_label(draw, "NOISE MAP — Bright=High Variance (Suspicious)", 10, 10)

        buf = io.BytesIO()
        blended.save(buf, "JPEG", quality=85)
        return buf.getvalue()

    except Exception:
        return b""


def generate_annotated_findings(
    image_bytes: bytes,
    findings: List[Dict],
) -> bytes:
    """Draw bounding boxes and labels over suspicious regions."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        draw = ImageDraw.Draw(img)

        for i, finding in enumerate(findings[:15]):
            loc = finding.get("location")
            if not loc:
                continue

            x0 = int(loc.get("x0", 0))
            y0 = int(loc.get("y0", 0))
            x1 = int(loc.get("x1", 100))
            y1 = int(loc.get("y1", 100))

            finding_type = finding.get("type", "unknown")
            severity = finding.get("severity", "LOW")
            confidence = finding.get("confidence", 0.0)
            color = FINDING_COLORS.get(finding_type, SEVERITY_COLORS.get(severity, (255, 255, 0)))

            # Draw rectangle with 2px border
            for offset in range(3):
                draw.rectangle(
                    [x0 - offset, y0 - offset, x1 + offset, y1 + offset],
                    outline=color,
                )

            # Label
            label = f"{finding_type} ({confidence:.0%})"
            label_y = max(0, y0 - 18)
            _draw_label(draw, label, x0, label_y, bg_color=color, text_color=(255, 255, 255))

        # Title
        _draw_label(draw, "FORENSIC FINDINGS — Highlighted Regions", 10, 10)

        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        return buf.getvalue()

    except Exception:
        return b""


def generate_forensic_report(
    image_bytes: bytes,
    findings: List[Dict],
    ela_quality: int = 90,
) -> bytes:
    """Generate a combined 2x2 forensic report image.

    Top-left: Original with annotations
    Top-right: ELA heatmap
    Bottom-left: Noise variance map
    Bottom-right: Summary panel
    """
    try:
        original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Target size for each quadrant
        target_w = max(400, original.width)
        target_h = max(300, original.height)

        # Generate individual panels
        annotated = _bytes_to_pil(generate_annotated_findings(image_bytes, findings), target_w, target_h)
        if annotated is None:
            annotated = original.copy().resize((target_w, target_h), Image.LANCZOS)

        ela_img = _bytes_to_pil(generate_ela_heatmap(image_bytes, ela_quality), target_w, target_h)
        if ela_img is None:
            ela_img = Image.new("RGB", (target_w, target_h), (30, 30, 30))

        noise_img = _bytes_to_pil(generate_noise_map(image_bytes), target_w, target_h)
        if noise_img is None:
            noise_img = Image.new("RGB", (target_w, target_h), (30, 30, 30))

        # Summary panel
        summary = _create_summary_panel(findings, target_w, target_h)

        # Compose 2x2 grid
        padding = 4
        full_w = target_w * 2 + padding * 3
        full_h = target_h * 2 + padding * 3 + 40  # extra for title

        canvas = Image.new("RGB", (full_w, full_h), (20, 22, 28))
        draw = ImageDraw.Draw(canvas)

        # Title bar
        _draw_label(draw, "PRAMAANAI — DOCUMENT FORENSIC ANALYSIS REPORT", full_w // 2 - 200, 8,
                    bg_color=(30, 130, 90), text_color=(255, 255, 255))

        y_offset = 40
        canvas.paste(annotated, (padding, y_offset))
        canvas.paste(ela_img, (target_w + padding * 2, y_offset))
        canvas.paste(noise_img, (padding, target_h + y_offset + padding))
        canvas.paste(summary, (target_w + padding * 2, target_h + y_offset + padding))

        buf = io.BytesIO()
        canvas.save(buf, "JPEG", quality=90)
        return buf.getvalue()

    except Exception:
        return b""


def _bytes_to_pil(data: bytes, target_w: int, target_h: int) -> Optional[Image.Image]:
    """Convert JPEG bytes to PIL Image, resized to target."""
    if not data:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img.resize((target_w, target_h), Image.LANCZOS)
    except Exception:
        return None


def _create_summary_panel(findings: List[Dict], width: int, height: int) -> Image.Image:
    """Create a text summary panel of findings."""
    panel = Image.new("RGB", (width, height), (25, 28, 35))
    draw = ImageDraw.Draw(panel)

    _draw_label(draw, "FINDINGS SUMMARY", 10, 10, bg_color=(50, 55, 65))

    # Count by severity
    high = sum(1 for f in findings if f.get("severity") == "HIGH")
    medium = sum(1 for f in findings if f.get("severity") == "MEDIUM")
    low = sum(1 for f in findings if f.get("severity") == "LOW")

    y = 40
    draw.text((15, y), f"Total findings: {len(findings)}", fill=(220, 220, 220))
    y += 22
    draw.text((15, y), f"HIGH severity: {high}", fill=(220, 60, 60))
    y += 22
    draw.text((15, y), f"MEDIUM severity: {medium}", fill=(240, 180, 30))
    y += 22
    draw.text((15, y), f"LOW severity: {low}", fill=(100, 180, 255))
    y += 32

    # Top findings
    draw.text((15, y), "Top findings:", fill=(180, 180, 180))
    y += 22

    for f in findings[:8]:
        if y > height - 25:
            break
        ftype = f.get("type", "unknown")[:35]
        conf = f.get("confidence", 0.0)
        sev = f.get("severity", "LOW")
        color = SEVERITY_COLORS.get(sev, (180, 180, 180))
        draw.text((15, y), f"  [{sev[0]}] {ftype}: {conf:.0%}", fill=color)
        y += 20

    if not findings:
        draw.text((15, y), "  No significant findings detected", fill=(100, 200, 100))

    # Disclaimer
    draw.text((15, height - 30),
              "Forensic indicators only — officer verification required",
              fill=(120, 120, 120))

    return panel


def _draw_label(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    bg_color: Tuple[int, int, int] = (30, 35, 45),
    text_color: Tuple[int, int, int] = (220, 220, 220),
) -> None:
    """Draw a labeled text with background rectangle."""
    # Estimate text size (default font)
    text_w = len(text) * 7
    text_h = 14
    draw.rectangle([x, y, x + text_w + 8, y + text_h + 6], fill=bg_color)
    draw.text((x + 4, y + 3), text, fill=text_color)
