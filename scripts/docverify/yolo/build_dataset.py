"""Build the YOLO11 region-detection dataset.

  train: real images (≈70%, deterministic split by sha256) + domain-randomised
         SYNTHETIC documents with exact boxes (training only)
  val:   real images only (≈30%) — every reported accuracy number comes
         from these held-out REAL images, never from synthetic ones.

Real images and boxes come from data/dataset_1 (gitignored personal data);
the built dataset goes to data/yolo/docverify (gitignored).

    .venv/bin/python -m scripts.docverify.yolo.build_dataset [--synthetic 300]
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.docverify import generate_synthetic_testset as G  # noqa: E402

REAL = ROOT / "data/dataset_1"
OUT = ROOT / "data/yolo/docverify"
CLASSES = ["document", "photograph", "mrz", "qr_code", "barcode", "stamp", "yellow_gold_feature"]
VAL_HEX = set("01234")  # sha256 first hex digit -> val (≈5/16 of images)


def write_label(path: Path, boxes: list[tuple[str, list[float]]]) -> None:
    lines = []
    for cls, (x0, y0, x1, y1) in boxes:
        x0, y0, x1, y1 = (min(1.0, max(0.0, v)) for v in (x0, y0, x1, y1))
        if x1 - x0 < 0.004 or y1 - y0 < 0.004:
            continue
        lines.append(f"{CLASSES.index(cls)} {(x0 + x1) / 2:.6f} {(y0 + y1) / 2:.6f} {x1 - x0:.6f} {y1 - y0:.6f}")
    path.write_text("\n".join(lines) + ("\n" if lines else ""))


# ------------------------------------------------------------ synthetic docs

def _rnd_name(r: random.Random) -> tuple[str, str]:
    given = r.choice(["ANANYA", "ARJUN", "MEERA", "KAVYA", "RAHUL", "PRIYA", "SONAM", "TASHI", "BIKASH", "SITA"])
    surname = r.choice(["SHARMA", "MEHTA", "RAO", "IYER", "DORJI", "THAPA", "GURUNG", "SINGH", "DAS", "KUMAR"])
    return given + " SYNTHETIC", surname


def _mrz_box(img_w: int, img_h: int, line1: str, y: int) -> list[float]:
    f = G.font(34, "m")
    w = f.getlength(line1)
    return [30 / img_w, (y - 6) / img_h, (40 + w + 10) / img_w, (y + 56 + 44) / img_h]


def synth_passport(r: random.Random):
    given, surname = _rnd_name(r)
    num = r.choice("ZNPXK") + "".join(str(r.randint(0, 9)) for _ in range(7))
    code = r.choice(["IND", "NPL", "BTN", "ITA"])
    img = G.make_passport(face_idx=r.randint(0, 60), surname=surname, given=given, number=num, code=code,
                          nat=code, nat_text={"IND": "INDIAN", "NPL": "NEPALI", "BTN": "BHUTANESE", "ITA": "ITALIAN"}[code],
                          dob=f"19{r.randint(60, 99)}-0{r.randint(1, 9)}-1{r.randint(0, 9)}",
                          expiry=f"20{r.randint(27, 35)}-0{r.randint(1, 9)}-2{r.randint(0, 8)}")
    W, H = img.size
    l1 = G.td3(code, surname, given, num, code, "1990-01-01", "F", "2030-01-01")[0]
    boxes = [("document", [0, 0, 1, 1]), ("photograph", [0.03, 0.19, 0.31, 0.77]),
             ("mrz", _mrz_box(W, H, l1, int(0.80 * H)))]
    return img, boxes


def synth_dl(r: random.Random):
    W, H = 1100, 700
    given, surname = _rnd_name(r)
    photo_pos = (int(0.74 * W), int(0.21 * H))
    with_qr = r.random() < 0.7
    dl = {"face": r.randint(0, 60), "number": f"MH{r.randint(10, 49)}20{r.randint(10, 24)}{r.randint(1000000, 9999999)}",
          "name": f"{given} {surname}", "dob": "1990-05-05", "issue": "2019-06-10", "expiry": "2039-05-04",
          "qr": G.dl_qr_payload("MH1220190012345", "X", "1990-05-05", "2039-05-04", signed=False) if with_qr else None,
          "gold": r.random() < 0.85, "photo_pos": photo_pos}
    img = G.driving_licence(dl)
    boxes = [("document", [0, 0, 1, 1]),
             ("photograph", [photo_pos[0] / W, photo_pos[1] / H, (photo_pos[0] + int(0.22 * W)) / W, (photo_pos[1] + int(0.43 * H)) / H])]
    if dl["gold"]:
        boxes.append(("yellow_gold_feature", [0.05, 0.32, 0.18, 0.53]))
    if with_qr:
        boxes.append(("qr_code", [0.80, 0.68, (0.80 * W + 200) / W, (0.68 * H + 200) / H]))
    return img, boxes


def synth_visa(r: random.Random):
    img = G.nepal_visa({"visa_number": f"T{r.randint(100000000, 999999999)}", "passport_number": "X1234567",
                        "valid_from": "2026-09-01", "valid_until": "2026-11-29", "qr": True})
    W, H = img.size
    return img, [("document", [0, 0, 1, 1]), ("qr_code", [0.66, 0.22, (0.66 * W + 260) / W, (0.22 * H + 260) / H])]


def synth_stamp_page(r: random.Random):
    W, H = 1000, 1300
    stamps, boxes = [], [("document", [0, 0, 1, 1])]
    names = ["KAKARBHITTA", "BIRGUNJ", "BHAIRAHAWA", "NEPALGUNJ", "PHUENTSHOLING", "RAXAUL", "SUNAULI", "DHANGADHI"]
    y = 120
    for _ in range(r.randint(1, 3)):
        shape = r.choice(["rect", "ellipse"])
        size = (r.randint(330, 470), r.randint(200, 320)) if shape == "rect" else (r.randint(300, 420),) * 2
        colour = r.choice([(40, 60, 170), (170, 30, 40), (120, 30, 140), (30, 110, 60), (20, 20, 20)])
        lines = [r.choice(["NEPAL IMMIGRATION", "IMMIGRATION", "BHUTAN IMMIGRATION", "BUREAU OF IMMIGRATION"]),
                 r.choice(names), r.choice(["ARRIVAL", "DEPARTURE", "ENTRY", "EXIT"]),
                 f"{r.randint(1, 28):02d} {r.choice(['JAN', 'MAR', 'JUN', 'SEP', 'NOV'])} 20{r.randint(18, 26)}"]
        st = G.stamp(lines, shape=shape, colour=colour, size=size)
        st = st.rotate(r.uniform(-25, 25), expand=True)
        x = r.randint(30, max(31, W - st.width - 30))
        if y + st.height > H - 30:
            break
        stamps.append((st, (x, y)))
        boxes.append(("stamp", [x / W, y / H, (x + st.width) / W, (y + st.height) / H]))
        y += st.height + r.randint(20, 120)
    return G.stamp_page(stamps), boxes


def synth_aadhaar(r: random.Random):
    img = G.aadhaar_like({"face": r.randint(0, 60), "name": " ".join(_rnd_name(r)), "dob": "1995-01-01",
                          "number": "2345 6789 0124"})
    W, H = img.size
    return img, [("document", [0, 0, 1, 1]), ("photograph", [0.03, 0.19, 0.29, 0.74]),
                 ("qr_code", [0.74, 0.18, (0.74 * W + 250) / W, (0.18 * H + 250) / H])]


def randomise(img: Image.Image, boxes, r: random.Random):
    """Place the document on a random background with perspective, rotation,
    lighting, blur and JPEG noise; transform boxes with the same matrix."""
    doc = np.asarray(img.convert("RGB"))
    h, w = doc.shape[:2]
    scale = r.uniform(0.55, 0.95)
    Wc, Hc = max(w + 10, int(w / scale)), max(h + 10, int(h / scale * r.uniform(0.9, 1.3)))
    bg_col = np.array([r.randint(20, 235) for _ in range(3)], np.float32)
    bg = np.clip(bg_col + np.random.default_rng(r.randint(0, 10**6)).normal(0, r.uniform(3, 25), (Hc, Wc, 3)), 0, 255).astype(np.uint8)
    ox, oy = r.randint(0, Wc - w), r.randint(0, Hc - h)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    j = 0.06
    dst = np.float32([[ox + r.uniform(-j, j) * w, oy + r.uniform(-j, j) * h], [ox + w + r.uniform(-j, j) * w, oy + r.uniform(-j, j) * h],
                      [ox + w + r.uniform(-j, j) * w, oy + h + r.uniform(-j, j) * h], [ox + r.uniform(-j, j) * w, oy + h + r.uniform(-j, j) * h]])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(doc, M, (Wc, Hc))
    mask = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (Wc, Hc))
    out = np.where(mask[..., None] > 0, warped, bg)
    # lighting gradient + contrast
    gx = np.linspace(r.uniform(0.7, 1.1), r.uniform(0.8, 1.2), Wc)[None, :, None]
    out = np.clip(out.astype(np.float32) * gx * r.uniform(0.8, 1.15) + r.uniform(-20, 20), 0, 255).astype(np.uint8)
    pil = Image.fromarray(out)
    if r.random() < 0.4:
        pil = pil.filter(ImageFilter.GaussianBlur(r.uniform(0.3, 1.6)))
    new_boxes = []
    for cls, (x0, y0, x1, y1) in boxes:
        pts = np.float32([[[x0 * w, y0 * h]], [[x1 * w, y0 * h]], [[x1 * w, y1 * h]], [[x0 * w, y1 * h]]])
        tp = cv2.perspectiveTransform(pts, M).reshape(-1, 2)
        new_boxes.append((cls, [tp[:, 0].min() / Wc, tp[:, 1].min() / Hc, tp[:, 0].max() / Wc, tp[:, 1].max() / Hc]))
    import io
    buf = io.BytesIO()
    pil.save(buf, "JPEG", quality=r.randint(45, 95))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB"), new_boxes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", type=int, default=300)
    args = ap.parse_args()
    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)

    labels = {r["file"]: r for r in json.loads((REAL / "labels.json").read_text())["records"] if not r["exclude"]}
    boxes = json.loads((REAL / "boxes.json").read_text())["boxes"]
    counts = {"train_real": 0, "val_real": 0, "train_synthetic": 0}
    split_record = {}
    for i, (name, bxs) in enumerate(sorted(boxes.items())):
        split = "val" if labels[name]["sha256"][0] in VAL_HEX else "train"
        img = ImageOps.exif_transpose(Image.open(REAL / "Dataset" / name)).convert("RGB")
        stem = f"real_{i:03d}"
        img.save(OUT / "images" / split / f"{stem}.jpg", quality=95)
        write_label(OUT / "labels" / split / f"{stem}.txt", [(b["cls"], b["box"]) for b in bxs])
        counts[f"{split}_real"] += 1
        split_record[stem] = {"file": name, "split": split}

    r = random.Random(1234)
    makers = [synth_passport, synth_dl, synth_dl, synth_visa, synth_stamp_page, synth_stamp_page, synth_aadhaar]
    for k in range(args.synthetic):
        img, bxs = r.choice(makers)(r)
        img, bxs = randomise(img, bxs, r)
        img.save(OUT / "images/train" / f"syn_{k:04d}.jpg", quality=92)
        write_label(OUT / "labels/train" / f"syn_{k:04d}.txt", bxs)
        counts["train_synthetic"] += 1

    (OUT / "dataset.yaml").write_text(
        f"path: {OUT}\ntrain: images/train\nval: images/val\nnames:\n" +
        "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    (OUT / "split.json").write_text(json.dumps({"counts": counts, "real": split_record}, indent=1))
    print(counts)


if __name__ == "__main__":
    main()
