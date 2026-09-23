"""Stamp pipeline:

    detected stamp region (YOLO, or classical candidate)
      -> crop -> OCR -> stamp type from text
      -> country / authority from text patterns (reference_data/*/stamps.json)
      -> checkpoint from the official checkpoint reference
      -> direction, date, visa/permit/reference numbers

Principles enforced here:
  * OCR alone never decides that something is a stamp — only a detected
    region is analysed. A classical candidate with no stamp-like text and no
    detector class is discarded as "not a stamp", not reported as one.
  * Colour and shape are never used to identify country or border type.
  * A land-border identification requires the checkpoint to be found in the
    official reference with checkpoint_type LAND_BORDER — never from shape.
  * Missing information is listed in `missing_fields`; nothing is invented.
"""
from __future__ import annotations

import re

import numpy as np

from app.services.docverify import reference
from app.services.docverify.fields import find_dates
from app.services.docverify.ocr import mean_confidence, ocr_region
from app.services.docverify.types import OcrLine, Region, StampResult, StampType


def _contains(text: str, patterns: list[str]) -> str | None:
    compact = re.sub(r"[^A-Z]", "", text)
    for p in sorted(patterns, key=len, reverse=True):
        if re.search(r"(?<![A-Z])" + re.escape(p) + r"(?![A-Z])", text):
            return p
        # OCR often drops spaces ("BUREAUOFIMMIGRATION"); multi-word phrases
        # (long enough to be unambiguous) also match without spaces.
        if " " in p and len(p.replace(" ", "")) >= 9 and p.replace(" ", "") in compact:
            return p
    return None


def _lines_inside(lines: list[OcrLine], bbox: list[int]) -> list[OcrLine]:
    out = []
    for l in lines:
        cx, cy = (l.bbox[0] + l.bbox[2]) / 2, (l.bbox[1] + l.bbox[3]) / 2
        if bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]:
            out.append(l)
    return out


def analyze_stamp(rgb: np.ndarray, region: Region, page_lines: list[OcrLine]) -> StampResult | None:
    """Image path. Returns None when a classical candidate turns out not to be a stamp."""
    inside = _lines_inside(page_lines, region.bbox)
    # Page OCR first: when the page-level lines inside the stamp already
    # identify it completely, the (expensive, upscaled) crop OCR adds
    # nothing and is skipped. Otherwise the crop is read as well — crop OCR
    # is upscaled and usually reads small stamp text better — and the union
    # of both is used.
    crop_lines: list[OcrLine] = []
    result = identify_stamp(" ".join(l.text for l in inside), region, mean_confidence(inside)) if inside else None
    if result is None or result.identification != "IDENTIFIED":
        crop_lines = ocr_region(rgb, region.bbox)
        seen = {l.text.upper() for l in crop_lines}
        lines = crop_lines + [l for l in inside if l.text.upper() not in seen]
        result = identify_stamp(" ".join(l.text for l in lines), region, mean_confidence(lines))
    if result is None:
        return None
    import cv2
    result.visual = stamp_visual_features(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), region.bbox, crop_lines or inside)
    result.reference_match, ref_notes = compare_visual_reference(result)
    result.notes.extend(ref_notes)
    return result


def identify_stamp(raw_text: str, region: Region, ocr_confidence: float) -> StampResult | None:
    """Text path (shared with on-device extraction): identify type, country,
    authority, checkpoint, direction and date from a detected stamp's text."""
    text = re.sub(r"\s+", " ", raw_text.upper())

    detector_label = region.meta.get("detector_label")
    best_ref = None
    country = authority = None
    for ref in reference.stamp_references():
        v = ref["versions"][0]
        c = _contains(text, v["country_text_patterns"])
        a = _contains(text, v["authority_text_patterns"])
        if c or a:
            score = (2 if c else 0) + (1 if a else 0)
            if best_ref is None or score > best_ref[0]:
                best_ref = (score, ref, c, a)
    if best_ref:
        _, ref, c, a = best_ref
        country = ref["country"] if c else None
        authority = a
    patterns = reference.stamp_references()[0]["versions"][0]

    direction = None
    for d, words in patterns["direction_patterns"].items():
        # Single-letter-ish tokens (IN/OUT) only count as a whole word.
        if any(re.search(rf"\b{re.escape(w)}\b", text) for w in words if len(w) > 3):
            direction = d
            break

    match = reference.match_checkpoint(text, country=None)
    checkpoint = match["record"] if match else None

    dates = find_dates(text)
    visa_no = re.search(r"VISA\s*(?:NO|NUMBER)?\.?\s*[:#]?\s*([A-Z0-9]{5,14})", text)
    permit_no = re.search(r"PERMIT\s*(?:NO|NUMBER)\.?\s*[:#]?\s*([A-Z0-9/-]{4,20})", text)
    ref_no = re.search(r"\b(?:NO|REF)\.?\s*[:#]?\s*([A-Z]{0,3}\d{2,6})\b", text)

    stamp_type = StampType.UNKNOWN_STAMP
    if _contains(text, patterns["stamp_type_patterns"]["PERMIT_MARKING"]):
        stamp_type = StampType.PERMIT_MARKING
    elif _contains(text, patterns["stamp_type_patterns"]["VISA_STAMP"]) and not direction:
        stamp_type = StampType.VISA_STAMP
    elif direction == "ENTRY" and authority:
        stamp_type = StampType.ENTRY_STAMP
    elif direction == "EXIT" and authority:
        stamp_type = StampType.EXIT_STAMP
    elif authority or direction:
        stamp_type = StampType.IMMIGRATION_STAMP

    # A classical candidate is only kept as a stamp if it carries evidence
    # of an immigration event — a date, a direction, or an immigration/
    # permit authority. Coloured printed headings ("GOVERNMENT OF NEPAL")
    # carry none of these and are discarded. A circular impression with any
    # legible text is kept as UNKNOWN_STAMP for the officer to examine. A
    # trained detector's stamp class is trusted as a region, not a verdict.
    event_evidence = bool(dates or direction or authority or stamp_type == StampType.PERMIT_MARKING)
    circular = region.source.endswith("hough-circle")
    legible = len(re.sub(r"[^A-Z0-9]", "", text)) >= 4
    if not detector_label and not event_evidence and not (circular and legible):
        return None

    notes: list[str] = [f"region proposed by {region.source}"]
    typed_label = detector_label if detector_label in StampType.__members__ and detector_label != "UNKNOWN_STAMP" else None
    if typed_label and stamp_type != StampType.UNKNOWN_STAMP:
        if typed_label != stamp_type.value and not (typed_label == "IMMIGRATION_STAMP" and stamp_type in (StampType.ENTRY_STAMP, StampType.EXIT_STAMP)):
            notes.append(f"detector class {typed_label} differs from text-derived type {stamp_type.value}")
    elif typed_label:
        stamp_type = StampType(typed_label)
        notes.append("stamp type taken from the detector class; text did not confirm it")

    checkpoint_country = checkpoint["country"] if checkpoint else None
    if checkpoint and country and checkpoint_country != country:
        notes.append(f"stamp text names country {country} but checkpoint {checkpoint['checkpoint_name']} "
                     f"belongs to {checkpoint_country} in the official reference")

    result = StampResult(
        region_id=region.id, stamp_type=stamp_type, identification="UNIDENTIFIED",
        country=country or checkpoint_country, authority=authority,
        checkpoint=checkpoint["checkpoint_name"] if checkpoint else None,
        checkpoint_id=checkpoint["checkpoint_id"] if checkpoint else None,
        checkpoint_type=checkpoint["checkpoint_type"] if checkpoint else None,
        direction=direction, date=dates[0][0] if dates else None,
        visa_number=visa_no.group(1) if visa_no else None,
        permit_number=permit_no.group(1) if permit_no else None,
        reference_number=ref_no.group(1) if ref_no else None,
        ocr_text=text[:400], ocr_confidence=ocr_confidence, detector_label=detector_label, notes=notes,
    )
    if checkpoint and country is None:
        result.notes.append("country inferred from the matched checkpoint's reference record, not from stamp text")
    if match:
        result.notes.append(f"checkpoint matched on {match['matched_text']!r} (similarity {match['similarity']})")

    core = {"country": result.country, "authority": authority, "checkpoint": result.checkpoint,
            "direction": direction, "date": result.date}
    result.missing_fields = [k for k, v in core.items() if not v]
    if not result.missing_fields and stamp_type != StampType.UNKNOWN_STAMP:
        result.identification = "IDENTIFIED"
    elif len(result.missing_fields) < len(core):
        result.identification = "PARTIALLY_IDENTIFIED"

    result.bbox = region.bbox
    identified = {"IDENTIFIED": 1.0, "PARTIALLY_IDENTIFIED": 0.7, "UNIDENTIFIED": 0.4}[result.identification]
    result.confidence = round(min(0.99, 0.5 * region.confidence + 0.5 * identified * max(result.ocr_confidence, 0.3)), 3)
    return result


# ------------------------------------------------------------ visual analysis

_HUE_NAMES = [(10, "red"), (25, "orange"), (35, "yellow"), (85, "green"), (130, "blue"), (160, "violet"), (180, "red")]


def stamp_visual_features(bgr: np.ndarray, bbox: list[int], text_lines: list[OcrLine]) -> dict:
    """Descriptive geometry of a stamp impression. Recorded as evidence and
    compared with a visual reference only where one exists — colour and shape
    are never used to identify country or border type."""
    import cv2

    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = max(0, bbox[0]), max(0, bbox[1]), min(w, bbox[2]), min(h, bbox[3])
    crop = bgr[y0:y1, x0:x1]
    if crop.size == 0:
        return {}
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    ink = ((hsv[..., 1] > 60) & (hsv[..., 2] < 245)) | (gray < 90)
    ink_u8 = ink.astype(np.uint8) * 255
    closed = cv2.morphologyEx(ink_u8, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    shape, orientation, aspect = "irregular", 0.0, (x1 - x0) / max(1, y1 - y0)
    border = "none_detected"
    if contours:
        outer = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(outer)
        peri = cv2.arcLength(outer, True)
        circularity = 4 * np.pi * area / (peri * peri) if peri else 0
        rect = cv2.minAreaRect(outer)
        (rw, rh), angle = rect[1], rect[2]
        rect_fill = area / max(1.0, rw * rh)
        approx = cv2.approxPolyDP(outer, 0.02 * peri, True)
        if circularity > 0.78:
            shape = "circular" if 0.85 < rw / max(1, rh) < 1.18 else "elliptical"
        elif len(approx) == 4 and rect_fill > 0.8:
            shape = "rectangular"
        elif len(approx) in (6, 8) and rect_fill > 0.7:
            shape = "polygonal"
        orientation = float(angle if angle <= 45 else angle - 90)
        # Border structure: walk inward from each of the four edges along the
        # middle row/column and count separate ink runs before the text area
        # (first 25% of the span). 1 run = single outline, 2+ = double.
        runs = []
        hh, ww = ink_u8.shape
        profiles = [ink_u8[hh // 2, : ww // 4], ink_u8[hh // 2, ww - ww // 4:][::-1],
                    ink_u8[: hh // 4, ww // 2], ink_u8[hh - hh // 4:, ww // 2][::-1]]
        for prof in profiles:
            on = prof > 0
            runs.append(int(np.count_nonzero(on[1:] & ~on[:-1]) + (1 if on.size and on[0] else 0)))
        edge_runs = sorted(runs)[len(runs) // 2] if runs else 0
        if edge_runs >= 2:
            border = "double_outline"
        elif edge_runs == 1:
            border = "single_outline"
        elif rect_fill < 0.5 or circularity > 0.6:
            border = "open_or_partial_outline"

    # Text arrangement: straight text lines are near-horizontal (or all share
    # one tilt); text on an arc produces a spread of line angles.
    angles = []
    for l in text_lines:
        bw, bh = l.bbox[2] - l.bbox[0], l.bbox[3] - l.bbox[1]
        if bw > 0:
            angles.append(np.degrees(np.arctan2(bh, bw)))
    arrangement = "unknown"
    if len(angles) >= 2:
        arrangement = "curved_or_mixed" if np.std(angles) > 12 else "linear"
    elif len(angles) == 1:
        arrangement = "single_line"

    hue_vals = hsv[..., 0][ink & (hsv[..., 1] > 60)]
    colour = "dark/black ink"
    if hue_vals.size > 50:
        med = float(np.median(hue_vals))
        colour = next(name for limit, name in _HUE_NAMES if med <= limit)
    return {
        "shape": shape,
        "aspect_ratio": round(aspect, 3),
        "orientation_degrees": round(orientation, 1),
        "relative_size": round(((x1 - x0) * (y1 - y0)) / (w * h), 4),
        "relative_position": [round(x0 / w, 3), round(y0 / h, 3), round(x1 / w, 3), round(y1 / h, 3)],
        "text_arrangement": arrangement,
        "border_structure": border,
        "dominant_ink_colour": colour,
        "colour_note": "Recorded as a descriptive characteristic only; never used to identify country or authenticity.",
    }


def compare_visual_reference(stamp: StampResult) -> tuple[str, list[str]]:
    """Compare geometry with a stamp visual reference for this checkpoint +
    direction. Only the clearly-labelled SYNTHETIC test references exist in
    this build, so real stamps return REFERENCE_NOT_AVAILABLE."""
    refs = reference.stamp_visual_references()
    key = f"{stamp.checkpoint_id}:{stamp.direction}" if stamp.checkpoint_id and stamp.direction else None
    ref = refs.get(key) if key else None
    if ref is None:
        return "REFERENCE_NOT_AVAILABLE", ["no authoritative visual reference for this stamp in the reference dataset"]
    v = stamp.visual
    diffs: list[str] = []
    if ref.get("shape") and v.get("shape") != ref["shape"]:
        diffs.append(f"shape {v.get('shape')!r} differs from reference {ref['shape']!r}")
    if ref.get("text_arrangement") and v.get("text_arrangement") not in (ref["text_arrangement"], "unknown", "single_line"):
        diffs.append(f"text arrangement {v.get('text_arrangement')!r} differs from reference {ref['text_arrangement']!r}")
    lo, hi = ref.get("aspect_ratio_range", [0, 99])
    if not lo <= v.get("aspect_ratio", 1) <= hi:
        diffs.append(f"aspect ratio {v.get('aspect_ratio')} outside reference range {lo}-{hi}")
    if ref.get("border_structure") and v.get("border_structure") not in (ref["border_structure"],):
        diffs.append(f"border {v.get('border_structure')!r} differs from reference {ref['border_structure']!r}")
    return ("MISMATCH" if diffs else "MATCH"), diffs or [f"geometry consistent with reference {ref['reference_id']} ({ref['data_classification']})"]
