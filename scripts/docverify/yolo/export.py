"""Export the trained region detector to ONNX for the Android app and check
that ONNX Runtime reproduces the PyTorch detections.

    .venv/bin/python -m scripts.docverify.yolo.export

Writes android/app/src/main/assets/pramaan_regions_yolo11n.onnx (opset 12,
static 640x640 input, output [1, 4 + classes, 8400]).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
WEIGHTS = ROOT / "models/yolo/pramaan_regions_yolo11n.pt"
ASSET = ROOT / "android/app/src/main/assets/pramaan_regions_yolo11n.onnx"


def letterbox(img: np.ndarray, size: int = 640) -> np.ndarray:
    import cv2
    h, w = img.shape[:2]
    r = min(size / w, size / h)
    nw, nh = int(w * r), int(h * r)
    canvas = np.full((size, size, 3), 114, np.uint8)
    px, py = (size - nw) // 2, (size - nh) // 2
    canvas[py:py + nh, px:px + nw] = cv2.resize(img, (nw, nh))
    return canvas


def main() -> None:
    import onnxruntime as ort
    from PIL import Image
    from ultralytics import YOLO

    model = YOLO(str(WEIGHTS))
    onnx_path = Path(model.export(format="onnx", imgsz=640, opset=12, simplify=True, dynamic=False))
    ASSET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(onnx_path, ASSET)

    # Parity: decode ONNX output exactly as OnDeviceRegionDetector.kt does
    # (letterbox, best class per anchor, per-class NMS) and match the boxes
    # against PyTorch predictions by IoU on every held-out real image.
    sess = ort.InferenceSession(str(ASSET), providers=["CPUExecutionProvider"])
    names = model.names
    matched = total_torch = total_onnx = 0
    out = None
    for sample in sorted((ROOT / "data/yolo/docverify/images/val").glob("*.jpg")):
        rgb = np.asarray(Image.open(sample).convert("RGB"))
        h, w = rgb.shape[:2]
        r = min(640 / w, 640 / h)
        px, py = (640 - int(w * r)) / 2, (640 - int(h * r)) / 2
        x = letterbox(rgb).astype(np.float32).transpose(2, 0, 1)[None] / 255.0
        out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0]
        dets = []
        for a in range(out.shape[1]):
            c = int(out[4:, a].argmax())
            sc = float(out[4 + c, a])
            if sc < 0.35:
                continue
            cx, cy, bw, bh = out[:4, a]
            dets.append((names[c], sc, [(cx - bw / 2 - px) / r, (cy - bh / 2 - py) / r, (cx + bw / 2 - px) / r, (cy + bh / 2 - py) / r]))
        kept = []
        for label in {d[0] for d in dets}:
            pool = sorted([d for d in dets if d[0] == label], key=lambda d: -d[1])
            while pool:
                top = pool.pop(0)
                kept.append(top)
                pool = [d for d in pool if _iou(d[2], top[2]) <= 0.5]
        ref = model.predict(str(sample), imgsz=640, conf=0.35, iou=0.5, verbose=False)[0].boxes
        ref_boxes = [(names[int(c)], b.tolist()) for c, b in zip(ref.cls, ref.xyxy)]
        total_torch += len(ref_boxes)
        total_onnx += len(kept)
        matched += sum(1 for lab, b in ref_boxes if any(k[0] == lab and _iou(k[2], b) > 0.7 for k in kept))
    print(f"parity over held-out images: torch boxes={total_torch}, onnx(android decode) boxes={total_onnx}, "
          f"matched(IoU>0.7)={matched}")
    print(f"exported {ASSET} ({ASSET.stat().st_size / 1e6:.1f} MB), output shape {None if out is None else out.shape}")


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


if __name__ == "__main__":
    main()
