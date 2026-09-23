"""Evaluate the PHONE path end to end on the server: what the Android app
sends (region crops only) versus verifying the full image.

For every synthetic document image this replays RegionCropper.prepare()
from the Android app exactly — detector regions (never the "document" box)
padded by 40% of their longest side + 8 px, then printed-text blocks padded
by 6 px, each added only while the union of crops stays under the 85%
coverage cap — and sends the result through verify_region_crops().

Differences from a real phone, stated plainly:
  * detections come from the same YOLO11n weights the app ships (the .pt
    the ONNX was exported from), run by ultralytics instead of ONNX Runtime;
  * ML Kit text *blocks* are approximated by PP-OCR text lines merged into
    blocks (lines that overlap vertically and sit close together).

Run: .venv/bin/python -m scripts.docverify.device_path_eval
"""
from __future__ import annotations

import base64
import json
import logging
import sys
from datetime import date
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
logging.disable(logging.WARNING)

from app.services.docverify.detection import decode_image  # noqa: E402
from app.services.docverify.ocr import ocr_image  # noqa: E402
from app.services.docverify.pipeline import verify_images, verify_region_crops  # noqa: E402

SYN = ROOT / "data/synthetic/docverify"
WEIGHTS = ROOT / "models/yolo/pramaan_regions_yolo11n.pt"
MAX_COVERAGE = 0.85
REGION_PAD_FRACTION = 0.40
TEXT_PAD_PX = 6


def _text_blocks(rgb: np.ndarray) -> list[list[int]]:
    """PP-OCR lines merged into paragraph-like blocks (ML Kit returns blocks)."""
    boxes = sorted((l.bbox for l in ocr_image(rgb)), key=lambda b: (b[1], b[0]))
    blocks: list[list[int]] = []
    for b in boxes:
        h = b[3] - b[1]
        for blk in blocks:
            near_x = b[0] < blk[2] + h and b[2] > blk[0] - h
            near_y = b[1] <= blk[3] + 0.6 * h
            if near_x and near_y:
                blk[:] = [min(blk[0], b[0]), min(blk[1], b[1]), max(blk[2], b[2]), max(blk[3], b[3])]
                break
        else:
            blocks.append(list(b))
    return blocks


def prepare(bgr: np.ndarray, detections: list[tuple[str, list[int], float]], blocks: list[list[int]],
            max_coverage: float = MAX_COVERAGE) -> tuple[list[dict], float, int]:
    """Port of RegionCropper.prepare()."""
    h, w = bgr.shape[:2]
    covered = np.zeros((h, w), bool)
    crops: list[dict] = []

    def add(label: str, tight: list[int], pad: int, conf: float) -> bool:
        x0, y0 = max(0, tight[0] - pad), max(0, tight[1] - pad)
        x1, y1 = min(w, tight[2] + pad), min(h, tight[3] + pad)
        if x1 - x0 < 8 or y1 - y0 < 8:
            return False
        trial = covered.copy()
        trial[y0:y1, x0:x1] = True
        if trial.mean() > max_coverage:
            return False
        covered[:] = trial
        ok, jpg = cv2.imencode(".jpg", bgr[y0:y1, x0:x1], [cv2.IMWRITE_JPEG_QUALITY, 92])
        crops.append({"label": label, "bbox": tight, "crop_bbox": [x0, y0, x1, y1], "confidence": conf,
                      "image_b64": base64.b64encode(jpg.tobytes()).decode()})
        return True

    for label, box, score in sorted((d for d in detections if d[0] != "document"), key=lambda d: -d[2]):
        add(label, box, int(REGION_PAD_FRACTION * max(box[2] - box[0], box[3] - box[1])) + 8, score)
    dropped = sum(0 if add("text", b, TEXT_PAD_PX, 0.9) else 1 for b in blocks)
    return crops, float(covered.mean()), dropped


def main() -> None:
    from ultralytics import YOLO
    model = YOLO(str(WEIGHTS))
    gt = json.loads((SYN / "ground_truth.json").read_text())
    seen: set[str] = set()
    rows = []
    for case in gt["cases"]:
        for name in case["images"]:
            if name in seen:
                continue
            seen.add(name)
            data = (SYN / name).read_bytes()
            bgr, rgb = decode_image(data)
            res = model.predict(bgr, conf=0.35, verbose=False)[0]
            dets = [(str(res.names[int(b.cls)]).lower(), [int(v) for v in b.xyxy[0].tolist()], float(b.conf))
                    for b in res.boxes]
            blocks = _text_blocks(rgb)
            crops, coverage, dropped = prepare(bgr, dets, blocks)
            travel = date.fromisoformat(case["options"]["travel_date"])
            full = verify_images([data], travel_date=travel)
            dev, _ = verify_region_crops({"documents": [{"image_size": [bgr.shape[1], bgr.shape[0]], "regions": crops,
                                                         "device_detector": "yolo11n (eval replay)"}],
                                          "travel_date": travel.isoformat()})
            ff = {k: v.value for k, v in full.documents[0].fields.items()}
            df = {k: v.value for k, v in dev.documents[0].fields.items()}
            lost = sorted(k for k in ff if k not in df)
            differ = sorted(k for k in ff if k in df and ff[k].replace(" ", "") != df[k].replace(" ", ""))
            full_regions = sorted({r.label.value for r in full.documents[0].regions})
            dev_regions = sorted({r.label.value for r in dev.documents[0].regions})
            rows.append({"image": name, "text_blocks": len(blocks), "text_dropped": dropped,
                         "coverage": round(coverage, 2), "fields_full": len(ff), "fields_device": len(df),
                         "lost": lost, "differ": differ,
                         "type_full": full.documents[0].document_type.document_type.value,
                         "type_device": dev.documents[0].document_type.document_type.value,
                         "status_full": full.overall_status.value, "status_device": dev.overall_status.value,
                         "extra_regions_device": sorted(set(dev_regions) - set(full_regions))})
            r = rows[-1]
            print(f"{name:34s} blocks {r['text_blocks']:2d} dropped {r['text_dropped']:2d} cov {r['coverage']:.2f} "
                  f"fields {r['fields_full']:2d}->{r['fields_device']:2d} lost={','.join(lost) or '-'} "
                  f"type {r['type_full']}->{r['type_device']} status {r['status_full']}->{r['status_device']} "
                  f"extra={','.join(r['extra_regions_device']) or '-'}", flush=True)
    n = len(rows)
    summary = {
        "images": n,
        "images_with_dropped_text": sum(1 for r in rows if r["text_dropped"]),
        "fields_full": sum(r["fields_full"] for r in rows),
        "fields_device": sum(r["fields_device"] for r in rows),
        "fields_lost": sum(len(r["lost"]) for r in rows),
        "fields_differ": sum(len(r["differ"]) for r in rows),
        "doc_type_agree": sum(r["type_full"] == r["type_device"] for r in rows),
        "status_agree": sum(r["status_full"] == r["status_device"] for r in rows),
    }
    print(json.dumps(summary, indent=2))
    out = ROOT / "reports/device_path_eval.json"
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
