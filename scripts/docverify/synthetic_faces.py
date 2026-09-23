"""Procedurally drawn synthetic portraits for the synthetic test set.

These are NOT photographs of anyone: each face is drawn from geometric
primitives with per-seed variation (skin tone, face shape, eye spacing,
hair, lips). They exist so photo detection, layout and face-comparison code
paths can be exercised without putting any real person's likeness on a
(synthetic) identity document. Face-matching accuracy measured on these is
NOT representative of performance on real photographs.
"""
from __future__ import annotations

import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SKIN = [(224, 188, 160), (198, 150, 118), (170, 120, 90), (140, 96, 70), (235, 200, 175), (120, 82, 60)]
HAIR = [(30, 25, 20), (60, 40, 25), (90, 60, 35), (20, 20, 20), (120, 90, 50), (45, 35, 30)]


def synthetic_face(seed: int, size: tuple[int, int] = (300, 380), variant: int = 0) -> Image.Image:
    """`variant` > 0 gives a different capture of the SAME synthetic person
    (small pose/lighting/expression changes), for positive match controls."""
    r = random.Random(seed)
    W, H = 600, 760
    bg = (r.randint(170, 215), r.randint(185, 225), r.randint(200, 235))
    img = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(img)
    skin, hair = SKIN[seed % len(SKIN)], HAIR[(seed * 7) % len(HAIR)]
    fw, fh = r.randint(170, 280), r.randint(250, 330)
    eye_dx, eye_y = r.randint(50, 92), r.randint(-22, 22)
    eye_w, eye_h = r.randint(20, 38), r.randint(9, 18)
    nose_len, mouth_w = r.randint(40, 85), r.randint(30, 70)
    glasses, beard, long_hair = r.random() < 0.35, r.random() < 0.3, r.random() < 0.45
    vr = random.Random(seed * 100 + variant)
    ox, oy = (vr.randint(-10, 10), vr.randint(-8, 8)) if variant else (0, 0)
    cx, cy = W // 2 + ox, 330 + oy
    # shoulders / neck
    d.ellipse((cx - 250, cy + 250, cx + 250, cy + 620), fill=(r.randint(30, 90), r.randint(40, 90), r.randint(60, 120)))
    d.rectangle((cx - 55, cy + 170, cx + 55, cy + 300), fill=tuple(int(c * 0.9) for c in skin))
    # hair back, ears, face
    d.ellipse((cx - fw // 2 - 22, cy - fh // 2 - 45, cx + fw // 2 + 22, cy + (fh // 2 + 120 if long_hair else fh // 4)), fill=hair)
    d.ellipse((cx - fw // 2 - 18, cy - 30, cx - fw // 2 + 18, cy + 45), fill=skin)
    d.ellipse((cx + fw // 2 - 18, cy - 30, cx + fw // 2 + 18, cy + 45), fill=skin)
    d.ellipse((cx - fw // 2, cy - fh // 2, cx + fw // 2, cy + fh // 2), fill=skin)
    # fringe
    d.chord((cx - fw // 2 - 5, cy - fh // 2 - 30, cx + fw // 2 + 5, cy - fh // 2 + 95), 180, 360, fill=hair)
    # eyebrows, eyes
    ey = cy - 25 + eye_y
    for sx in (-1, 1):
        ex = cx + sx * eye_dx
        d.line((ex - 34, ey - 34, ex + 30, ey - 38 + sx * 2), fill=tuple(int(c * 0.8) for c in hair), width=9)
        d.ellipse((ex - eye_w, ey - eye_h, ex + eye_w, ey + eye_h), fill=(245, 245, 240))
        iris = (r.randint(40, 90), r.randint(30, 70), r.randint(20, 50))
        gaze = vr.randint(-3, 3) if variant else 0
        d.ellipse((ex - 13 + gaze, ey - 13, ex + 13 + gaze, ey + 13), fill=iris)
        d.ellipse((ex - 6 + gaze, ey - 6, ex + 6 + gaze, ey + 6), fill=(10, 10, 10))
        d.arc((ex - eye_w, ey - eye_h - 2, ex + eye_w, ey + eye_h + 2), 190, 350, fill=(60, 40, 30), width=3)
        if glasses:
            d.rounded_rectangle((ex - eye_w - 12, ey - eye_h - 12, ex + eye_w + 12, ey + eye_h + 12), radius=10,
                                outline=(20, 20, 20), width=5)
    # nose
    nose = tuple(int(c * 0.82) for c in skin)
    d.line((cx, ey + 5, cx - 10, ey + nose_len), fill=nose, width=5)
    d.arc((cx - 24, ey + nose_len - 15, cx + 24, ey + nose_len + 15), 20, 160, fill=nose, width=5)
    # mouth / beard
    my = ey + nose_len + r.randint(35, 60)
    if beard:
        d.chord((cx - fw // 2 + 10, my - 40, cx + fw // 2 - 10, cy + fh // 2 + 10), 0, 180, fill=hair)
    lip = (r.randint(150, 190), r.randint(70, 100), r.randint(80, 110))
    smile = vr.randint(0, 8) if variant else 0
    d.chord((cx - mouth_w, my - 16, cx + mouth_w, my + 20 + smile), 0, 180, fill=lip)
    d.line((cx - mouth_w + 2, my + 1, cx + mouth_w - 2, my + 1), fill=tuple(int(c * 0.6) for c in lip), width=3)
    # shading
    arr = np.asarray(img).astype(np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    light = 1.0 - 0.18 * ((xx - (cx - 90 + (15 if variant else 0))) / W) ** 2 * 4
    arr *= light[..., None]
    if variant:
        arr = arr * (1.0 + 0.05 * variant) + 4
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.3))
    noise = np.random.default_rng(seed * 13 + variant).normal(0, 3.0, (H, W, 3))
    img = Image.fromarray(np.clip(np.asarray(img) + noise, 0, 255).astype(np.uint8))
    return img.resize(size, Image.LANCZOS)
