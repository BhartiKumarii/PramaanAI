"""Deterministic QR / barcode decoding (OpenCV's QRCodeDetector and
barcode.BarcodeDetector). No language model is ever asked to "read" a code.

Payload handling is deliberately conservative:
  * Aadhaar Secure QR (a very long all-digit string) is recognised as a
    UIDAI-signed payload and NOT decompressed, parsed or otherwise opened —
    it must be verified through UIDAI's official mechanism.
  * Structured payloads (JSON / key=value / legacy XML attributes) are parsed
    into fields for comparison with the printed text.
  * Anything else is kept as opaque text with only its length recorded.
"""
from __future__ import annotations

import json
import re
from typing import Any

import cv2
import numpy as np

from app.services.docverify.types import MachineReadableCode, Region, RegionLabel

_FIELD_ALIASES = {
    "document_number": {"doc_no", "document_number", "docno", "dl_no", "dlno", "licence_number", "license_number",
                        "licence_no", "license_no", "permit_no", "permit_number", "visa_no", "visa_number", "uid"},
    "passport_number": {"passport_no", "passport_number", "ppt_no"},
    "name": {"name", "full_name", "holder_name", "nm"},
    "date_of_birth": {"dob", "date_of_birth", "birth_date", "yob"},
    "date_of_expiry": {"expiry", "date_of_expiry", "valid_until", "valid_till", "doe", "expiry_date"},
    "valid_from": {"valid_from", "issue_date", "doi"},
    "nationality": {"nationality", "nat"},
}


def _norm_key(key: str) -> str | None:
    k = re.sub(r"[^a-z_]", "", key.lower().replace(" ", "_"))
    for canonical, aliases in _FIELD_ALIASES.items():
        if k in aliases:
            return canonical
    return None


def parse_payload(text: str) -> tuple[str, dict[str, str]]:
    """Classify and parse a decoded payload. Returns (payload_kind, fields)."""
    stripped = text.strip()
    if re.fullmatch(r"\d{200,}", stripped):
        return "SIGNED_SECURE_QR", {}
    if stripped.startswith("{"):
        try:
            data: Any = json.loads(stripped)
        except ValueError:
            data = None
        if isinstance(data, dict) and "sig" in data and isinstance(data.get("payload"), dict):
            # Signed envelope: fields come from the signed payload; the
            # signature itself is verified in signatures.py, never here.
            _, inner = parse_payload(json.dumps(data["payload"]))
            return "SIGNED_STRUCTURED", inner
        if isinstance(data, dict):
            fields: dict[str, str] = {}
            for key, value in data.items():
                canonical = _norm_key(str(key))
                if canonical and value not in (None, ""):
                    fields.setdefault(canonical, str(value))
            if "schema" in data:
                fields["schema"] = str(data["schema"])
            return "STRUCTURED", fields
    if "<PrintLetterBarcodeData" in stripped or stripped.startswith("<?xml"):
        # Legacy (unsigned) XML QR: plain attributes, no cryptography involved.
        fields = {}
        for key, value in re.findall(r'(\w+)="([^"]*)"', stripped):
            canonical = _norm_key(key)
            if canonical:
                fields.setdefault(canonical, value)
        return "LEGACY_XML", fields
    pairs = re.findall(r"([A-Za-z_ ]{2,30})\s*[:=]\s*([^;|\n]+)", stripped)
    if len(pairs) >= 2:
        fields = {}
        for key, value in pairs:
            canonical = _norm_key(key.strip())
            if canonical:
                fields.setdefault(canonical, value.strip())
        if fields:
            return "STRUCTURED", fields
    return "TEXT", {}


def _bbox_from_points(points: np.ndarray, pad: int = 4) -> list[int]:
    pts = points.reshape(-1, 2)
    return [int(pts[:, 0].min()) - pad, int(pts[:, 1].min()) - pad,
            int(pts[:, 0].max()) + pad, int(pts[:, 1].max()) + pad]


def detect_and_decode(bgr: np.ndarray, id_prefix: str = "code",
                      raw_out: dict[str, str] | None = None) -> tuple[list[Region], list[MachineReadableCode]]:
    """Decode every QR / barcode. Raw payload text goes only into `raw_out`
    (used transiently for signature verification) — it is never persisted."""
    regions: list[Region] = []
    codes: list[MachineReadableCode] = []

    def add(label: RegionLabel, symbology: str, bbox: list[int], text: str | None, method: str) -> None:
        rid = f"{id_prefix}-{len(regions) + 1}"
        decoded = bool(text)
        kind, fields = parse_payload(text) if decoded else ("UNREADABLE", {})
        if raw_out is not None and decoded:
            raw_out[rid] = text
        regions.append(Region(id=rid, label=label, bbox=bbox, confidence=1.0 if decoded else 0.6,
                              source=f"classical:{method}", meta={"decoded": decoded, "symbology": symbology}))
        codes.append(MachineReadableCode(region_id=rid, symbology=symbology, decoded=decoded,
                                         payload_kind=kind, fields=fields, raw_length=len(text or "")))

    # Camera photos of cards defeat the detector at native resolution more
    # often than not; retry on a 2x sharpened and an adaptive-threshold
    # variant. A code that is located but never decoded is still reported
    # (present, UNREADABLE) — never silently dropped, never guessed.
    qr = cv2.QRCodeDetector()
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    sharp2x = cv2.filter2D(cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC), -1,
                           np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], np.float32))
    adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 10)
    located: tuple[np.ndarray, str] | None = None
    for image, scale, variant in ((bgr, 1.0, "raw"), (sharp2x, 2.0, "2x-sharpened"), (adaptive, 1.0, "adaptive-threshold")):
        try:
            ok, texts, points, _ = qr.detectAndDecodeMulti(image)
        except cv2.error:
            ok, texts, points = False, (), None
        if ok and points is not None and any(texts):
            for text, pts in zip(texts, points):
                add(RegionLabel.QR_CODE, "QR_CODE", _bbox_from_points(pts / scale), text or None, f"opencv-qrcode:{variant}")
            break
        # The single-code decoder succeeds on some images where the
        # multi-code one fails outright.
        try:
            text, pts, _ = qr.detectAndDecode(image)
        except cv2.error:
            text, pts = "", None
        if text and pts is not None:
            add(RegionLabel.QR_CODE, "QR_CODE", _bbox_from_points(pts / scale), text, f"opencv-qrcode:{variant}")
            break
        # Locate-only fallback skips the 2x image: it is the slowest pass
        # (profiled) and the raw/adaptive passes locate the same codes.
        if located is None and scale == 1.0:
            try:
                found, pts = qr.detect(image)
            except cv2.error:
                found, pts = False, None
            if found and pts is not None:
                located = (pts / scale, variant)
    else:
        if located is not None:
            add(RegionLabel.QR_CODE, "QR_CODE", _bbox_from_points(located[0]), None, f"opencv-qrcode:{located[1]}")

    if hasattr(cv2, "barcode"):
        try:
            detector = cv2.barcode.BarcodeDetector()
            result = detector.detectAndDecodeWithType(bgr)
            ok, infos, types, pts = (result if len(result) == 4 else (result[0], result[1], result[2], result[3]))
        except (cv2.error, ValueError, TypeError):
            ok, infos, types, pts = False, (), (), None
        if ok and pts is not None:
            for info, sym, p in zip(infos, types, pts):
                bbox = _bbox_from_points(np.asarray(p))
                # Skip a "barcode" that is actually the QR we already decoded.
                if any(_iou(bbox, r.bbox) > 0.3 for r in regions):
                    continue
                add(RegionLabel.BARCODE, str(sym) or "BARCODE", bbox, info or None, "opencv-barcode")
    return regions, codes


def _iou(a: list[int], b: list[int]) -> float:
    ix0, iy0, ix1, iy1 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0
