"""EXIF / image metadata forensic analysis.

Checks image metadata for signs of editing (software tags, inconsistent
timestamps, unusual dimensions). Missing metadata is NOT treated as
evidence of forgery — many legitimate document scans/photos lack EXIF.
"""
import io
import logging
from datetime import datetime

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

from app.services.tampering.base import TamperingFinding

logger = logging.getLogger("pramaan.forensics.metadata")

_EDITING_SOFTWARE = [
    "photoshop", "gimp", "paint.net", "affinity", "pixlr",
    "lightroom", "capture one", "darktable", "rawtherapee",
    "snapseed", "picsart", "fotor", "canva",
    "adobe", "corel", "imagemagick", "irfanview",
]


def _extract_exif(img: Image.Image) -> dict:
    try:
        raw_exif = img.getexif()
        if not raw_exif:
            return {}

        decoded = {}
        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8", errors="replace")
                except Exception:
                    value = str(value)
            decoded[tag_name] = value

        for ifd_id in [0x8769, 0x8825]:
            try:
                ifd_data = raw_exif.get_ifd(ifd_id)
                if ifd_data:
                    tag_map = GPSTAGS if ifd_id == 0x8825 else TAGS
                    for tag_id, value in ifd_data.items():
                        tag_name = tag_map.get(tag_id, str(tag_id))
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8", errors="replace")
                            except Exception:
                                value = str(value)
                        decoded[tag_name] = value
            except Exception:
                pass

        return decoded
    except Exception:
        return {}


def _parse_exif_datetime(dt_str: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(str(dt_str).strip(), fmt)
        except (ValueError, TypeError):
            continue
    return None


def _estimate_jpeg_quality(image_bytes: bytes) -> int | None:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        qtables = img.quantization
        if not qtables:
            return None
        table = list(qtables.values())[0]
        avg_q = sum(table) / len(table)
        return max(1, min(100, int(100 - avg_q * 0.8)))
    except Exception:
        return None


def analyze_metadata(image_bytes: bytes) -> list[TamperingFinding]:
    findings: list[TamperingFinding] = []

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        logger.debug("Cannot open image for metadata: %s", e)
        return findings

    w, h = image.size

    if w < 100 or h < 100:
        findings.append(TamperingFinding(
            type="metadata_low_resolution",
            confidence=0.3,
            reason=f"Image dimensions {w}×{h} are unusually small for a document scan",
            location=None,
        ))

    aspect = w / h if h > 0 else 0.0
    if aspect > 4.0 or aspect < 0.2:
        findings.append(TamperingFinding(
            type="metadata_unusual_aspect",
            confidence=0.25,
            reason=f"Aspect ratio {aspect:.2f} ({w}×{h}) is atypical for identity documents",
            location=None,
        ))

    exif = _extract_exif(image)

    if not exif:
        findings.append(TamperingFinding(
            type="metadata_absent",
            confidence=0.0,
            reason="No EXIF metadata present — this is normal for scanned "
                   "documents and does not indicate tampering",
            location=None,
        ))
        return findings

    # --- Editing software check ---
    for field_name in ("Software", "ProcessingSoftware", "ImageDescription"):
        value = exif.get(field_name)
        if not value or not isinstance(value, str):
            continue
        sw_lower = value.lower()
        for editor in _EDITING_SOFTWARE:
            if editor in sw_lower:
                findings.append(TamperingFinding(
                    type="metadata_editing_software",
                    confidence=0.45,
                    reason=f"EXIF {field_name} tag contains '{value}' — "
                           f"image was processed with editing software "
                           f"(may be legitimate post-processing)",
                    location=None,
                ))
                break

    # --- Timestamp consistency ---
    timestamps: dict[str, datetime] = {}
    for tag in ("DateTime", "DateTimeOriginal", "DateTimeDigitized"):
        raw = exif.get(tag)
        if raw:
            dt = _parse_exif_datetime(raw)
            if dt:
                timestamps[tag] = dt

    if len(timestamps) >= 2:
        ts_list = list(timestamps.values())
        max_gap = max(
            abs((a - b).total_seconds())
            for i, a in enumerate(ts_list)
            for b in ts_list[i + 1:]
        )
        if max_gap > 86400:
            tag_summary = ", ".join(f"{k}={v.isoformat()}" for k, v in timestamps.items())
            findings.append(TamperingFinding(
                type="metadata_timestamp_gap",
                confidence=round(min(0.6, max_gap / 604800), 4),
                reason=f"EXIF timestamps differ by {max_gap / 3600:.1f} hours: "
                       f"{tag_summary} — may indicate re-save or metadata modification",
                location=None,
            ))

    modification = exif.get("DateTime")
    creation = exif.get("DateTimeOriginal") or exif.get("DateTimeDigitized")
    if modification and not creation:
        findings.append(TamperingFinding(
            type="metadata_missing_original_timestamp",
            confidence=0.2,
            reason="Modification timestamp present but original capture timestamp "
                   "missing — possible re-save (common in many workflows)",
            location=None,
        ))

    # --- Resolution consistency ---
    x_res = exif.get("XResolution")
    y_res = exif.get("YResolution")
    if x_res and y_res:
        try:
            x_val = float(x_res) if not isinstance(x_res, tuple) else x_res[0] / x_res[1]
            y_val = float(y_res) if not isinstance(y_res, tuple) else y_res[0] / y_res[1]
            if abs(x_val - y_val) > 1:
                findings.append(TamperingFinding(
                    type="metadata_resolution_mismatch",
                    confidence=0.4,
                    reason=f"X and Y resolution differ ({x_val} vs {y_val} DPI) — "
                           f"possible resize or crop manipulation",
                    location=None,
                ))
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    # --- JPEG quality estimation ---
    quality = _estimate_jpeg_quality(image_bytes)
    if quality is not None:
        if quality > 98:
            findings.append(TamperingFinding(
                type="metadata_very_high_quality",
                confidence=0.15,
                reason=f"Very high JPEG quality ({quality}%) — unusual for camera "
                       f"capture, may indicate re-save from lossless source",
                location=None,
            ))
        elif quality < 50:
            findings.append(TamperingFinding(
                type="metadata_heavy_compression",
                confidence=0.35,
                reason=f"Heavy JPEG compression ({quality}%) — may obscure "
                       f"tampering evidence or indicate multiple re-saves",
                location=None,
            ))

    return findings
