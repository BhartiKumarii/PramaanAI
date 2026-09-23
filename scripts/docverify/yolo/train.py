"""Train the YOLO11n region detector and evaluate it on held-out REAL images.

    .venv/bin/python -m scripts.docverify.yolo.train [--epochs 60]

Outputs:
  models/yolo/pramaan_regions_yolo11n.pt   (server: PRAMAAN_YOLO_WEIGHTS)
  reports/yolo_region_detector.json         (per-class P/R/mAP on real val)
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/yolo/docverify/dataset.yaml"
OUT_WEIGHTS = ROOT / "models/yolo/pramaan_regions_yolo11n.pt"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()
    from ultralytics import YOLO

    model = YOLO("yolo11n.pt")  # COCO-pretrained backbone; detection head retrained for our 7 classes
    model.train(data=str(DATA), epochs=args.epochs, imgsz=args.imgsz, batch=16, device="cpu", workers=4,
                project=str(ROOT / "runs/docverify"), name="yolo11n_regions", exist_ok=True,
                fliplr=0.0, degrees=5.0, perspective=0.0005, patience=25, seed=0, deterministic=True, plots=True)
    best = ROOT / "runs/docverify/yolo11n_regions/weights/best.pt"
    OUT_WEIGHTS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(best, OUT_WEIGHTS)

    metrics = YOLO(str(OUT_WEIGHTS)).val(data=str(DATA), split="val", imgsz=args.imgsz, device="cpu", plots=False)
    names = metrics.names
    per_class = {}
    for i, c in enumerate(metrics.box.ap_class_index):
        p, r, ap50, ap = metrics.box.class_result(i)
        per_class[names[int(c)]] = {"precision": round(float(p), 3), "recall": round(float(r), 3),
                                    "mAP50": round(float(ap50), 3), "mAP50_95": round(float(ap), 3)}
    split = json.loads((ROOT / "data/yolo/docverify/split.json").read_text())
    report = {"model": "YOLO11n (ultralytics), fine-tuned from COCO weights", "epochs": args.epochs, "imgsz": args.imgsz,
              "train": {"real_images": split["counts"]["train_real"], "synthetic_images": split["counts"]["train_synthetic"]},
              "evaluated_on": f"{split['counts']['val_real']} held-out REAL images only (no synthetic images in val)",
              "overall": {"precision": round(float(metrics.box.mp), 3), "recall": round(float(metrics.box.mr), 3),
                          "mAP50": round(float(metrics.box.map50), 3), "mAP50_95": round(float(metrics.box.map), 3)},
              "per_class": per_class,
              "caveat": ("Small held-out set; boxes were labelled by Claude (auto-proposals reviewed image-by-image), "
                         "not by an independent annotator. Treat as indicative.")}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/yolo_region_detector.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
