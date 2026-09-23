"""Profile the verification pipeline per stage.

    .venv/bin/python -m scripts.docverify.profile_pipeline

Warms the models first (loading is a one-off cost), then profiles a fixed
set of real + synthetic images and prints wall time per image and the
cumulative time of the pipeline's own stages.
"""
from __future__ import annotations

import logging
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from app.services.docverify.pipeline import verify_images  # noqa: E402

IMAGES = [
    "data/dataset_1/Dataset/IMG_20260922_141824.jpg",   # Nepal passport (real)
    "data/dataset_1/Dataset/dl_18.jpg",                  # Indian DL with QR (real)
    "data/dataset_1/Dataset/IMG_20260922_203123.jpg",    # Nepal visa + stamp (real)
    "data/dataset_1/Dataset/IMG_20260923_155802.jpg",    # stamp pages (real)
    "data/synthetic/docverify/GEN-003_dl.jpg",           # synthetic DL (signed QR)
    "data/synthetic/docverify/GEN-002_stamp_page.jpg",   # synthetic stamp page
]
TIMES: dict[str, list[float]] = {}


def _wrap(module, attr: str, label: str | None = None) -> None:
    fn = getattr(module, attr)
    name = label or f"{module.__name__.rsplit('.', 1)[-1]}.{attr}"

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            TIMES.setdefault(name, []).append(time.perf_counter() - t0)
    setattr(module, attr, timed)


def instrument() -> None:
    from app.services.docverify import (border_rules, consistency, detection, doc_type, forensics, pipeline,
                                        security_features, stamps)
    for mod, attr in [(pipeline, "ocr_image"), (stamps, "ocr_region"), (pipeline, "detect_and_decode"),
                      (pipeline, "_decode_codes_in_regions"), (pipeline, "analyze_stamp"), (stamps, "stamp_visual_features"),
                      (pipeline, "_best_orientation"), (pipeline, "_quality"), (pipeline, "extract_fields"),
                      (pipeline, "assess_photo"), (pipeline, "_document_face_quality"), (pipeline, "verify_faces"),
                      (pipeline, "_image_checks"), (pipeline, "_document_checks"), (pipeline, "analyze_image"),
                      (forensics, "ForensicMaps"), (forensics, "analyze_region"), (forensics, "analyze_text_peers"),
                      (forensics, "find_duplicates"), (security_features, "assess_security_features"),
                      (security_features, "layout_consistency"), (doc_type, "classify"), (consistency, "run"),
                      (border_rules, "evaluate")]:
        _wrap(mod, attr)
    det = detection.get_region_detector()
    _wrap(det, "detect", "region_detector.detect (YOLO)")
    _wrap(detection, "detect_faces")


def main() -> None:
    instrument()
    blobs = [(p, (ROOT / p).read_bytes()) for p in IMAGES if (ROOT / p).exists()]
    verify_images([blobs[0][1]], travel_date=date(2026, 9, 23))  # warm-up: model loading
    TIMES.clear()
    total = 0.0
    for name, data in blobs:
        t0 = time.perf_counter()
        verify_images([data], travel_date=date(2026, 9, 23))
        dt = time.perf_counter() - t0
        total += dt
        print(f"{dt:6.2f}s  {name}")
    print(f"\ntotal {total:.1f}s for {len(blobs)} images — inclusive time per stage (nested stages overlap):")
    for name, ts in sorted(TIMES.items(), key=lambda kv: -sum(kv[1])):
        print(f"{sum(ts):7.2f}s  {100 * sum(ts) / total:5.1f}%  calls={len(ts):4d}  avg={sum(ts) / len(ts):.3f}s  {name}")


if __name__ == "__main__":
    main()
