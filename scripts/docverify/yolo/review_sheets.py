"""Render box-review sheets: each image with a 0.1 coordinate grid and the
numbered boxes from a boxes JSON, 4 images per sheet."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[3]
COLOURS = {"document": (120, 120, 120), "photograph": (0, 170, 0), "mrz": (0, 90, 255), "qr_code": (200, 0, 200),
           "barcode": (150, 0, 150), "stamp": (230, 60, 0), "yellow_gold_feature": (220, 180, 0)}


def render(boxes_file: str, out_dir: str, files: list[str] | None = None, cell: int = 760) -> list[str]:
    data = json.loads(Path(boxes_file).read_text())
    names = files or list(data)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    out = []
    for s in range(0, len(names), 4):
        sheet = Image.new("RGB", (cell * 2, cell * 2), "white")
        for k, name in enumerate(names[s:s + 4]):
            im = ImageOps.exif_transpose(Image.open(ROOT / "data/dataset_1/Dataset" / name)).convert("RGB")
            im.thumbnail((cell - 40, cell - 60))
            d = ImageDraw.Draw(im)
            w, h = im.size
            for i in range(1, 10):
                d.line((w * i / 10, 0, w * i / 10, h), fill=(0, 200, 255), width=1)
                d.line((0, h * i / 10, w, h * i / 10), fill=(0, 200, 255), width=1)
                d.text((w * i / 10 + 2, 2), f".{i}", font=small, fill=(0, 120, 200))
                d.text((2, h * i / 10 + 2), f".{i}", font=small, fill=(0, 120, 200))
            for j, b in enumerate(data.get(name, [])):
                x0, y0, x1, y1 = b["box"]
                c = COLOURS[b["cls"]]
                d.rectangle((x0 * w, y0 * h, x1 * w, y1 * h), outline=c, width=3)
                d.text((x0 * w + 3, y0 * h + 3), f"{j}:{b['cls'][:5]}", font=font, fill=c)
            x, y = (k % 2) * cell, (k // 2) * cell
            sheet.paste(im, (x + 20, y + 30))
            ImageDraw.Draw(sheet).text((x + 20, y + 6), f"[{s + k}] {name[:60]}", font=font, fill=(0, 0, 0))
        p = Path(out_dir) / f"review_{s // 4:02d}.jpg"
        sheet.save(p, quality=82)
        out.append(str(p))
    return out


if __name__ == "__main__":
    print("\n".join(render(sys.argv[1], sys.argv[2])))
