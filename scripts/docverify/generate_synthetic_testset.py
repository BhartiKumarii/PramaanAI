"""Generate the SYNTHETIC document-verification test set + ground truth.

Every document produced here is fictional and visibly marked
"SYNTHETIC SPECIMEN": invented names and numbers, generic layouts drawn
from the prototype templates in reference_data/ (not copies of any real
document's artwork). Portraits are procedurally DRAWN synthetic faces
(scripts/docverify/synthetic_faces.py) — no real person's likeness is used.
QR payloads are either plain synthetic JSON or signed with the TEST-ONLY
synthetic issuer key (app/services/docverify/signatures.py).

    .venv/bin/python -m scripts.docverify.generate_synthetic_testset

Writes data/synthetic/docverify/*.jpg and ground_truth.json. The output is
deterministic (fixed seed) so evaluation numbers are reproducible.
"""
from __future__ import annotations

import io
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.docverify.signatures import sign_synthetic  # noqa: E402
from scripts.docverify.synthetic_faces import synthetic_face  # noqa: E402
from app.services.validation.mrz import compute_check_digit  # noqa: E402

OUT = ROOT / "data/synthetic/docverify"
TRAVEL_DATE = "2026-09-23"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_M = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

rng = random.Random(20260923)


def font(size: int, kind: str = "r") -> ImageFont.FreeTypeFont:
    return ImageFont.truetype({"r": FONT, "b": FONT_B, "m": FONT_M}[kind], size)


def face(seed: int, size: tuple[int, int] = (260, 330), augment: bool = False) -> Image.Image:
    """Drawn synthetic portrait; `augment` = a different capture of the same synthetic person."""
    return synthetic_face(seed, size, variant=1 if augment else 0)


def guilloche(d: ImageDraw.ImageDraw, box: tuple[int, int, int, int], colour=(200, 215, 230)) -> None:
    x0, y0, x1, y1 = box
    for k in range(10):
        pts = [(x, y0 + (y1 - y0) * (0.5 + 0.45 * np.sin(x / (18 + 3 * k) + k))) for x in range(x0, x1, 3)]
        d.line(pts, fill=colour, width=1)


def specimen_banner(d: ImageDraw.ImageDraw, w: int) -> None:
    d.text((w - 330, 8), "SYNTHETIC SPECIMEN", font=font(20, "b"), fill=(200, 40, 40))


def label_value(d, x, y, label, value, size=24, lab_size=16):
    d.text((x, y), label, font=font(lab_size), fill=(70, 70, 90))
    d.text((x, y + lab_size + 4), value, font=font(size, "b"), fill=(20, 20, 30))


def qr(payload: str, size: int = 230) -> Image.Image:
    enc = cv2.QRCodeEncoder.create()
    m = enc.encode(payload)
    m = cv2.resize(m, (size, size), interpolation=cv2.INTER_NEAREST)
    return Image.fromarray(m).convert("RGB")


def yymmdd(iso: str) -> str:
    y, m, d = iso.split("-")
    return y[2:] + m + d


def td3(code: str, surname: str, given: str, number: str, nat: str, dob: str, sex: str, expiry: str,
        bad_check: str | None = None) -> tuple[str, str]:
    name = (surname.replace(" ", "<") + "<<" + given.replace(" ", "<"))[:39]
    l1 = f"P<{code}{name}".ljust(44, "<")
    num = number.ljust(9, "<")
    c_num, c_dob, c_exp = compute_check_digit(num), compute_check_digit(yymmdd(dob)), compute_check_digit(yymmdd(expiry))
    if bad_check == "dob":
        c_dob = (c_dob + 3) % 10
    personal = "<" * 14
    c_pers = "<"
    body = f"{num}{c_num}{nat}{yymmdd(dob)}{c_dob}{sex}{yymmdd(expiry)}{c_exp}{personal}{c_pers}"
    composite = compute_check_digit(f"{num}{c_num}{yymmdd(dob)}{c_dob}{yymmdd(expiry)}{c_exp}{personal}{c_pers}")
    return l1, body + str(composite)


def save(img: Image.Image, name: str, quality: int = 92) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT / name, "JPEG", quality=quality)
    return name


def jpeg_patch(img: Image.Image, q: int = 30) -> Image.Image:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=q)
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def add_noise(img: Image.Image, sigma: float) -> Image.Image:
    arr = np.asarray(img).astype(np.float32)
    arr += np.random.default_rng(7).normal(0, sigma, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ documents

def passport(p: dict) -> Image.Image:
    W, H = 1250, 880
    img = Image.new("RGB", (W, H), (244, 241, 232))
    d = ImageDraw.Draw(img)
    guilloche(d, (int(0.33 * W), int(0.15 * H), W - 10, int(0.75 * H)))
    specimen_banner(d, W)
    d.text((40, 30), p.get("title", "REPUBLIC OF INDIA"), font=font(30, "b"), fill=(30, 40, 90))
    d.text((40, 72), "PASSPORT", font=font(26, "b"), fill=(30, 40, 90))
    photo = face(p["face"], (int(0.28 * W), int(0.58 * H)))
    img.paste(photo, (int(0.03 * W), int(0.19 * H)))
    x = int(0.36 * W)
    label_value(d, x, 150, "Type / Country Code", f"P  {p['code']}")
    label_value(d, x + 420, 150, "Passport No.", p["number"])
    label_value(d, x, 215, "Surname", p["surname"])
    label_value(d, x, 280, "Given Names", p["given"])
    label_value(d, x, 345, "Nationality", p["nationality_text"])
    label_value(d, x + 420, 345, "Sex", p["sex"])
    label_value(d, x, 410, "Date of Birth", p["dob_printed"])
    label_value(d, x + 420, 410, "Place of Birth", p.get("pob", "SYNTHETIC CITY"))
    label_value(d, x, 475, "Date of Issue", p["issue_printed"])
    label_value(d, x + 420, 475, "Date of Expiry", p["expiry_printed"])
    if p.get("signature"):
        d.text((x + 420, 540), "Holder's Signature", font=font(16), fill=(70, 70, 90))
        d.line([(x + 430, 600), (x + 470, 575), (x + 500, 605), (x + 540, 570), (x + 590, 600)], fill=(20, 30, 90), width=4)
    if not p.get("no_mrz"):
        l1, l2 = p["mrz"]
        d.text((40, int(0.80 * H)), l1, font=font(34, "m"), fill=(10, 10, 10))
        d.text((40, int(0.80 * H) + 56), l2, font=font(34, "m"), fill=(10, 10, 10))
    return img


def dmy(iso: str) -> str:
    y, m, dd = iso.split("-")
    return f"{dd}/{m}/{y}"


def make_passport(face_idx=0, surname="SHARMA", given="ANANYA SYNTHETIC", number="Z1234567", code="IND",
                  nat="IND", nat_text="INDIAN", sex="F", dob="1996-04-12", issue="2021-05-10", expiry="2031-05-09",
                  printed: dict | None = None, mrz_override: dict | None = None, bad_check=None, title=None,
                  signature: bool = False, no_mrz: bool = False):
    printed = printed or {}
    mo = {"surname": surname, "given": given, "number": number, "dob": dob, "expiry": expiry, **(mrz_override or {})}
    return passport({
        "face": face_idx, "code": code, "number": printed.get("number", number), "surname": printed.get("surname", surname),
        "given": printed.get("given", given), "nationality_text": nat_text, "sex": sex,
        "dob_printed": dmy(printed.get("dob", dob)), "issue_printed": dmy(issue),
        "expiry_printed": dmy(printed.get("expiry", expiry)), "title": title or ("REPUBLIC OF INDIA" if code == "IND" else "REPUBLIC OF ITALY"),
        "mrz": td3(code, mo["surname"], mo["given"], mo["number"], nat, mo["dob"], sex, mo["expiry"], bad_check),
        "signature": signature, "no_mrz": no_mrz,
    })


def driving_licence(dl: dict) -> Image.Image:
    W, H = 1100, 700
    img = Image.new("RGB", (W, H), (236, 244, 238))
    d = ImageDraw.Draw(img)
    guilloche(d, (int(0.22 * W), int(0.20 * H), int(0.72 * W), int(0.95 * H)), (190, 220, 200))
    specimen_banner(d, W)
    d.text((30, 30), "UNION OF INDIA", font=font(22, "b"), fill=(20, 60, 40))
    d.text((30, 62), f"DRIVING LICENCE  ({dl.get('state', 'MAHARASHTRA')})", font=font(28, "b"), fill=(20, 60, 40))
    # yellow/gold chip-like VISUAL feature (generic drawing)
    if dl.get("gold", True):
        gx0, gy0, gx1, gy1 = int(0.05 * W), int(0.32 * H), int(0.18 * W), int(0.53 * H)
        d.rounded_rectangle((gx0, gy0, gx1, gy1), radius=12, fill=(212, 175, 55), outline=(150, 120, 30), width=3)
        for k in range(1, 4):
            y = gy0 + k * (gy1 - gy0) // 4
            d.line((gx0 + 8, y, gx1 - 8, y), fill=(150, 120, 30), width=2)
        d.line(((gx0 + gx1) // 2, gy0 + 8, (gx0 + gx1) // 2, gy1 - 8), fill=(150, 120, 30), width=2)
    # hologram-like rainbow region
    hx0, hy0 = int(0.05 * W), int(0.62 * H)
    for k in range(0, int(0.13 * W)):
        hue = int(180 * k / (0.13 * W))
        col = cv2.cvtColor(np.uint8([[[hue, 120, 235]]]), cv2.COLOR_HSV2RGB)[0][0]
        d.line((hx0 + k, hy0, hx0 + k, int(0.88 * H)), fill=tuple(int(c) for c in col))
    photo_pos = dl.get("photo_pos", (int(0.74 * W), int(0.21 * H)))
    if not dl.get("no_photo"):
        img.paste(face(dl["face"], (int(0.22 * W), int(0.43 * H))), photo_pos)
    x = int(0.24 * W)
    label_value(d, x, 150, "DL No", dl["number"])
    label_value(d, x, 215, "Name", dl["name"])
    label_value(d, x, 280, "Date of Birth", dmy(dl["dob"]))
    label_value(d, x, 345, "Date of Issue", dmy(dl["issue"]))
    label_value(d, x + 260, 345, "Valid Till", dmy(dl["expiry"]))
    label_value(d, x, 410, "COV", "  ".join(dl.get("cov", ["MCWG", "LMV"])))
    label_value(d, x, 475, "Licencing Authority", dl.get("authority", "RTO SYNTHETIC"))
    if dl.get("qr") is not None:
        img.paste(qr(dl["qr"], 200), (int(0.80 * W), int(0.68 * H)))
    return img


def dl_qr_payload(number, name, dob, expiry, signed=True, tamper_after=None):
    payload = {"schema": "PRAMAAN-SYNTHETIC-DL-v1", "dl_no": number, "name": name, "dob": dob, "valid_till": expiry}
    if not signed:
        return json.dumps(payload, separators=(",", ":"))
    env = json.loads(sign_synthetic(payload))
    if tamper_after:
        env["payload"].update(tamper_after)  # altered AFTER signing -> signature must fail
    return json.dumps(env, separators=(",", ":"))


def nepal_visa(v: dict) -> Image.Image:
    W, H = 1100, 700
    img = Image.new("RGB", (W, H), (246, 240, 246))
    d = ImageDraw.Draw(img)
    guilloche(d, (int(0.05 * W), int(0.25 * H), int(0.60 * W), int(0.95 * H)), (225, 205, 225))
    specimen_banner(d, W)
    d.text((40, 30), "GOVERNMENT OF NEPAL", font=font(32, "b"), fill=(120, 20, 40))
    d.text((40, 76), "TOURIST VISA", font=font(28, "b"), fill=(120, 20, 40))
    y = 150
    for lab, val in (("Visa No", v["visa_number"]), ("Visa Type", "TOURIST"), ("Passport No", v["passport_number"]),
                     ("Validity", f"{dmy(v['valid_from'])} to {dmy(v['valid_until'])}"), ("Entries", "MULTIPLE"),
                     ("Duration of Stay", "90 DAYS"), ("Issued at", "SYNTHETIC CONSULATE")):
        d.text((40, y), f"{lab}: {val}", font=font(26, "b"), fill=(20, 20, 30))
        y += 62
    if v.get("qr", True):
        img.paste(qr(json.dumps({"schema": "PRAMAAN-SYNTHETIC-VISA-v1", "visa_no": v["visa_number"],
                                  "passport_no": v["passport_number"], "valid_until": v["valid_until"]}), 260),
                  (int(0.66 * W), int(0.22 * H)))
    return img


def bhutan_permit(p: dict) -> Image.Image:
    W, H = 1100, 800
    img = Image.new("RGB", (W, H), (248, 246, 236))
    d = ImageDraw.Draw(img)
    specimen_banner(d, W)
    d.text((40, 30), "ROYAL GOVERNMENT OF BHUTAN", font=font(30, "b"), fill=(140, 70, 10))
    d.text((40, 74), "DEPARTMENT OF IMMIGRATION  -  ENTRY PERMIT", font=font(24, "b"), fill=(140, 70, 10))
    y = 150
    for lab, val in (("Permit No", p["permit_number"]), ("Name", p["name"]), ("Nationality", "INDIAN"),
                     ("Passport No", p["document_number"]), ("Valid From", dmy(p["valid_from"])),
                     ("Valid Until", dmy(p["valid_until"])), ("Purpose of Visit", "TOURISM"),
                     ("Issued at", "PHUENTSHOLING")):
        d.text((40, y), f"{lab}: {val}", font=font(26, "b"), fill=(20, 20, 30))
        y += 62
    img.paste(qr(sign_synthetic({"permit_no": p["permit_number"], "name": p["name"], "valid_until": p["valid_until"]}), 240),
              (int(0.74 * W), int(0.04 * H) + 60))
    return img


def aadhaar_like(a: dict) -> Image.Image:
    W, H = 1100, 700
    img = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(img)
    specimen_banner(d, W)
    d.text((40, 30), "GOVERNMENT OF INDIA", font=font(28, "b"), fill=(20, 20, 20))
    d.text((40, 70), "AADHAAR  (SYNTHETIC TEST CARD)", font=font(24, "b"), fill=(170, 60, 20))
    img.paste(face(a["face"], (int(0.26 * W), int(0.55 * H))), (int(0.03 * W), int(0.19 * H)))
    d.text((int(0.33 * W), 190), a["name"], font=font(30, "b"), fill=(20, 20, 20))
    d.text((int(0.33 * W), 245), f"DOB: {dmy(a['dob'])}", font=font(28, "b"), fill=(20, 20, 20))
    d.text((int(0.33 * W), 300), "FEMALE", font=font(26, "b"), fill=(20, 20, 20))
    d.text((int(0.33 * W), 560), a["number"], font=font(40, "b"), fill=(20, 20, 20))
    # Simulated Secure-QR presence: a long all-digit payload (random digits,
    # NOT a real UIDAI structure or signature).
    digits = "".join(str(rng.randrange(10)) for _ in range(900))
    img.paste(qr(digits, 250), (int(0.74 * W), int(0.18 * H)))
    return img


def stamp(lines: list[str], shape: str = "rect", colour=(40, 60, 170), size=(420, 230)) -> Image.Image:
    w, h = size
    s = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    if shape == "rect":
        d.rectangle((4, 4, w - 5, h - 5), outline=colour, width=5)
        d.rectangle((16, 16, w - 17, h - 17), outline=colour, width=3)
    else:
        d.ellipse((4, 4, w - 5, h - 5), outline=colour, width=6)
        d.ellipse((20, 20, w - 21, h - 21), outline=colour, width=3)
    fs = 30 if shape == "rect" else 24
    total = len(lines) * (fs + 8)
    y = (h - total) // 2
    for line in lines:
        tw = d.textlength(line, font=font(fs, "b"))
        d.text(((w - tw) / 2, y), line, font=font(fs, "b"), fill=colour)
        y += fs + 8
    return s


def stamp_page(stamps: list[tuple[Image.Image, tuple[int, int]]], pasted_jpeg: set[int] | None = None,
               duplicate: bool = False) -> Image.Image:
    W, H = 1000, 1300
    page = Image.new("RGB", (W, H), (245, 240, 225))
    d = ImageDraw.Draw(page)
    guilloche(d, (20, 20, W - 20, H - 20), (228, 222, 205))
    specimen_banner(d, W)
    d.text((40, 30), "VISAS / SYNTHETIC PASSPORT PAGE 7", font=font(22), fill=(120, 110, 90))
    for idx, (st, pos) in enumerate(stamps):
        if pasted_jpeg and idx in pasted_jpeg:
            bg = page.crop((pos[0], pos[1], pos[0] + st.width, pos[1] + st.height))
            bg.paste(st, (0, 0), st)
            patch = add_noise(jpeg_patch(bg.filter(ImageFilter.GaussianBlur(1.2)), 25), 6)
            page.paste(patch, pos)
        else:
            page.paste(st, pos, st)
    if duplicate:
        st, pos = stamps[0]
        region = page.crop((pos[0], pos[1], pos[0] + st.width, pos[1] + st.height))
        page.paste(region, (pos[0] + 60, pos[1] + 560))
    return page


# ------------------------------------------------------------------ cases

def build() -> list[dict]:
    cases: list[dict] = []

    def case(cid, desc, images, gt, **opts):
        cases.append({"case_id": cid, "description": desc, "images": images,
                      "options": {"travel_date": TRAVEL_DATE, **opts}, "ground_truth": gt})

    base_pp = dict(surname="SHARMA", given="ANANYA SYNTHETIC", number="Z1234567", dob="1996-04-12",
                   issue="2021-05-10", expiry="2031-05-09")
    pp_fields = {"document_number": "Z1234567", "date_of_birth": "1996-04-12", "date_of_expiry": "2031-05-09",
                 "surname": "SHARMA", "given_names": "ANANYA SYNTHETIC", "nationality": "INDIAN", "sex": "F"}
    gen_pp = save(make_passport(**base_pp), "GEN-001_passport.jpg")
    case("GEN-001", "Genuine synthetic Indian passport (matching mock registry record)", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["PASS"], "attention_required": False,
          "fields": {"0": pp_fields}, "tampered": False,
          "expected_checks": {"mrz_check_digits": ["PASS"], "mrz_consistency": ["PASS"], "registry": ["PASS"]}},
         border_route="INDIA_NEPAL")

    it_pp = save(make_passport(face_idx=1, surname="ROSSI", given="ELENA SYNTHETIC", number="X1234567", code="ITA",
                               nat="ITA", nat_text="ITALIAN", dob="1990-02-03", issue="2020-01-15", expiry="2030-01-14"),
                 "GEN-002_passport_ita.jpg")
    visa = save(nepal_visa({"visa_number": "T260044110", "passport_number": "X1234567",
                            "valid_from": "2026-09-01", "valid_until": "2026-11-29"}), "GEN-002_nepal_visa.jpg")
    kak = stamp(["NEPAL IMMIGRATION", "KAKARBHITTA", "ARRIVAL", "12 SEP 2026"])
    page_ok = save(stamp_page([(kak, (260, 250))]), "GEN-002_stamp_page.jpg")
    case("GEN-002", "Genuine synthetic Nepal visa with passport and Kakarbhitta arrival stamp (third-country traveller)",
         [it_pp, visa, page_ok],
         {"document_types": ["FOREIGN_PASSPORT", "NEPAL_VISA", "IMMIGRATION_STAMP"], "expected_overall": ["PASS"],
          "attention_required": False, "tampered": False,
          "fields": {"1": {"visa_number": "T260044110", "passport_number": "X1234567", "valid_from": "2026-09-01",
                           "date_of_expiry": "2026-11-29"}},
          "expected_checks": {"cross_document": ["PASS"], "visa_requirement": ["PASS"], "checkpoint_match": ["PASS"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    dl_ok = dict(face=2, number="MH1220190012345", name="ARJUN SYNTHETIC MEHTA", dob="1994-03-15", issue="2019-06-10",
                 expiry="2039-03-14")
    gen_dl = save(driving_licence({**dl_ok, "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"])}),
                  "GEN-003_dl.jpg")
    dl_fields = {"document_number": "MH1220190012345", "name": "ARJUN SYNTHETIC MEHTA", "date_of_birth": "1994-03-15",
                 "date_of_issue": "2019-06-10", "date_of_expiry": "2039-03-14"}
    case("GEN-003", "Genuine synthetic Indian driving licence (signed QR, yellow/gold visual feature, mock registry VALID)",
         [gen_dl], {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["PASS"], "attention_required": False,
                    "fields": {"0": dl_fields}, "tampered": False,
                    "expected_checks": {"digital_signature": ["PASS"], "qr_consistency": ["PASS"], "registry": ["PASS"],
                                        "yellow_gold_feature": ["PASS"]}})

    permit = save(bhutan_permit({"permit_number": "EP-2026-558812", "name": "KAVYA SYNTHETIC IYER",
                                 "document_number": "N0123456", "valid_from": "2026-09-20", "valid_until": "2026-09-27"}),
                  "GEN-004_bhutan_permit.jpg")
    case("GEN-004", "Genuine synthetic Bhutan entry permit (signed QR, mock registry ISSUED)", [permit],
         {"document_types": ["BHUTAN_ENTRY_PERMIT"], "expected_overall": ["PASS"], "attention_required": False,
          "fields": {"0": {"permit_number": "EP-2026-558812", "name": "KAVYA SYNTHETIC IYER"}}, "tampered": False,
          "expected_checks": {"digital_signature": ["PASS"], "registry": ["PASS"]}},
         border_route="INDIA_BHUTAN", direction="INDIA_TO_BHUTAN")

    aad = save(aadhaar_like({"face": 3, "name": "MEERA SYNTHETIC RAO", "dob": "1999-08-21", "number": "2345 6789 0124"}),
               "GEN-005_aadhaar_like.jpg")
    case("GEN-005", "Synthetic Aadhaar-like card: must route to official verification, never self-verify", [aad],
         {"document_types": ["AADHAAR"], "expected_overall": ["OFFICIAL_VERIFICATION_REQUIRED", "REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False,
          "expected_checks": {"aadhaar_official": ["OFFICIAL_VERIFICATION_REQUIRED"]}})

    # ---- mismatch / validation cases
    img = save(make_passport(**base_pp, printed={"number": "Z1234568"}), "TST-001_ocr_mrz_number.jpg")
    case("TST-001", "OCR/MRZ mismatch: printed passport number differs from MRZ", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED", "FAIL"], "attention_required": True,
          "tampered": False, "expected_checks": {"mrz_consistency": ["REVIEW_REQUIRED"]}})

    visa_bad = save(nepal_visa({"visa_number": "T260044110", "passport_number": "X1234568",
                                "valid_from": "2026-09-01", "valid_until": "2026-11-29"}), "TST-002_visa.jpg")
    case("TST-002", "Passport/visa mismatch: visa quotes a different passport number", [it_pp, visa_bad, page_ok],
         {"document_types": ["FOREIGN_PASSPORT", "NEPAL_VISA", "IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False, "expected_checks": {"cross_document": ["REVIEW_REQUIRED"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    dl_dob = save(driving_licence({**dl_ok, "dob": "1995-03-15", "qr": None}), "TST-003_dl_dob.jpg")
    case("TST-003", "DOB mismatch: printed DOB differs from the (mock) registry record", [dl_dob],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"registry_consistency": ["REVIEW_REQUIRED"]}})

    img = save(make_passport(**{**base_pp, "issue": "2015-05-10", "expiry": "2025-05-09"}), "TST-004_expired.jpg")
    case("TST-004", "Expired document", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED", "FAIL"], "attention_required": True,
          "tampered": False, "expected_checks": {"document_validity": ["FAIL"]}})

    img = save(driving_licence({**dl_ok, "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], "1994-03-25", dl_ok["expiry"], signed=False)}),
               "TST-005_dl_qr_mismatch.jpg")
    case("TST-005", "QR/OCR mismatch: unsigned QR DOB differs from printed DOB", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"qr_consistency": ["REVIEW_REQUIRED"]}})

    img = save(driving_licence({**dl_ok, "qr": None}), "TST-006_dl_no_qr.jpg")
    case("TST-006", "Missing QR on a template version that carries one", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"machine_readable_code": ["REVIEW_REQUIRED"]}})

    img = save(stamp_page([(kak, (260, 300))]), "TST-007_stamp.jpg")
    case("TST-007", "Stamp detection: Nepal immigration arrival stamp, Kakarbhitta", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["PASS"], "attention_required": False,
          "tampered": False, "stamp": {"country": "NEPAL", "checkpoint": "KAKARBHITTA", "direction": "ENTRY", "date": "2026-09-12"},
          "expected_checks": {"stamp_detection": ["PASS"], "stamp_identification": ["PASS"]}})

    unk = stamp(["APPROVED", "REF 00417"], shape="ellipse", colour=(150, 30, 120), size=(360, 250))
    img = save(stamp_page([(unk, (300, 350))]), "TST-008_unknown_stamp.jpg")
    case("TST-008", "Unknown stamp: impression with no identifiable authority, checkpoint or direction", [img],
         {"document_types": ["IMMIGRATION_STAMP", "DOCUMENT_TYPE_UNCERTAIN"], "expected_overall": ["REVIEW_REQUIRED", "NOT_VERIFIED"],
          "attention_required": True, "tampered": False})

    bir = stamp(["NEPAL IMMIGRATION", "BIRGUNJ", "ARRIVAL", "05 SEP 2026"])
    img = save(stamp_page([(bir, (260, 400))]), "TST-009_birgunj.jpg")
    case("TST-009", "Land-border checkpoint match: Birgunj (India–Nepal) arrival stamp", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "stamp": {"country": "NEPAL", "checkpoint": "BIRGUNJ", "direction": "ENTRY", "date": "2026-09-05",
                    "checkpoint_type": "LAND_BORDER"},
          "expected_checks": {"checkpoint_match": ["PASS"]}})

    bad_cp = stamp(["NEPAL IMMIGRATION", "JAIGAON", "ARRIVAL", "05 SEP 2026"])
    img = save(stamp_page([(bad_cp, (260, 400))]), "TST-010_checkpoint_mismatch.jpg")
    case("TST-010", "Checkpoint mismatch: stamp says NEPAL immigration but names an Indian (India–Bhutan) post", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"stamp_consistency": ["REVIEW_REQUIRED"]}})

    pp_img = make_passport(**base_pp)
    other = add_noise(jpeg_patch(face(10, (int(0.28 * 1250), int(0.58 * 880))).filter(ImageFilter.GaussianBlur(0.8)), 22), 9)
    pp_img.paste(other, (int(0.03 * 1250), int(0.19 * 880)))
    img = save(pp_img, "TST-011_photo_replaced.jpg")
    case("TST-011", "Synthetic photo replacement: portrait swapped with a re-compressed, noisier photo", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": True, "tamper_region": "PHOTOGRAPH", "expected_checks": {"tampering_analysis": ["REVIEW_REQUIRED"]}})

    dl_img = driving_licence({**dl_ok, "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"])})
    patch = Image.new("RGB", (240, 34), (228, 238, 230))
    ImageDraw.Draw(patch).text((2, 0), dmy(dl_ok["dob"]), font=font(25, "b"), fill=(35, 35, 45))
    patch = add_noise(jpeg_patch(patch, 18), 10)
    dl_img.paste(patch, (int(0.24 * 1100), 280 + 20))
    img = save(dl_img, "TST-012_text_manipulated.jpg")
    case("TST-012", "Image manipulation: DOB text region overwritten with a pasted, re-compressed patch", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": True, "tamper_region": "TEXT", "expected_checks": {"tampering_analysis": ["REVIEW_REQUIRED"]}})

    case("TST-013", "Registry unavailable: genuine licence, DL registry disabled", [gen_dl],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REGISTRY_NOT_AVAILABLE"], "attention_required": True,
          "tampered": False, "expected_checks": {"registry": ["REGISTRY_NOT_AVAILABLE"]}}, dl_registry_mode="disabled")

    poor = make_passport(**base_pp).filter(ImageFilter.GaussianBlur(6)).resize((420, 296))
    poor = Image.fromarray((np.asarray(poor).astype(np.float32) * 0.18).astype(np.uint8))
    img = save(poor, "TST-014_poor_quality.jpg", quality=40)
    case("TST-014", "Poor-quality image: blurred, dark, low resolution", [img],
         {"document_types": ["INDIAN_PASSPORT", "DOCUMENT_TYPE_UNCERTAIN"], "expected_overall": ["NOT_VERIFIED"],
          "attention_required": True, "tampered": False, "expected_checks": {"image_quality": ["NOT_VERIFIED"]}})

    case("TST-015", "Offline verification: genuine passport verified with no connectivity", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REGISTRY_NOT_AVAILABLE"], "attention_required": True,
          "tampered": False, "offline": True, "expected_checks": {"registry": ["REGISTRY_NOT_AVAILABLE"]}},
         offline=True, border_route="INDIA_NEPAL")

    img = save(make_passport(**base_pp, printed={"surname": "VERMA"}), "TST-016_name_mismatch.jpg")
    case("TST-016", "Name mismatch: printed surname differs from MRZ", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"mrz_consistency": ["REVIEW_REQUIRED"]}})

    img = save(make_passport(**base_pp, printed={"expiry": "2033-05-09"}), "TST-017_expiry_mismatch.jpg")
    case("TST-017", "Expiry mismatch: printed expiry differs from MRZ", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"mrz_consistency": ["REVIEW_REQUIRED"]}})

    img = save(make_passport(**base_pp, bad_check="dob"), "TST-018_mrz_checkdigit.jpg")
    case("TST-018", "MRZ mismatch: DOB check digit does not validate", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED", "FAIL"], "attention_required": True,
          "tampered": False, "expected_checks": {"mrz_check_digits": ["FAIL", "REVIEW_REQUIRED"]}})

    img = save(driving_licence({**dl_ok, "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"]),
                                "photo_pos": (int(0.36 * 1100), int(0.50 * 700)), "gold": True}), "TST-019_photo_position.jpg")
    case("TST-019", "Photo-position anomaly: portrait printed where the template expects text", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"photo": ["REVIEW_REQUIRED"]}})

    live_other = save(face(5, (400, 500)), "TST-020_live_other_person.jpg")
    case("TST-020", "Face mismatch: presented person differs from the passport photo", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "face_same": False, "expected_checks": {"face_verification": ["REVIEW_REQUIRED"]}},
         live_face=live_other)

    live_same = save(face(0, (400, 500), augment=True), "TST-021_live_same_person.jpg")
    case("TST-021", "Face match control: presented person is the passport holder (different capture)", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["PASS"], "attention_required": False,
          "tampered": False, "face_same": True, "expected_checks": {"face_verification": ["PASS"]}},
         live_face=live_same)

    kak_round = stamp(["NEPAL IMMIGRATION", "KAKARBHITTA", "ARRIVAL", "12 SEP 2026"], shape="ellipse", size=(470, 330))
    img = save(stamp_page([(kak_round, (240, 300))]), "TST-022_stamp_reference_mismatch.jpg")
    case("TST-022", "Stamp-reference mismatch: Kakarbhitta arrival stamp with geometry unlike its (synthetic) reference",
         [img], {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
                 "tampered": False, "expected_checks": {"stamp_reference": ["REVIEW_REQUIRED"]}})

    img = save(stamp_page([(kak, (260, 250))], pasted_jpeg={0}, duplicate=True), "TST-023_stamp_forensics.jpg")
    case("TST-023", "Stamp image-forensics anomaly: stamp pasted as a re-compressed patch and duplicated", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": True, "tamper_region": "STAMP", "expected_checks": {"stamp_forensics": ["REVIEW_REQUIRED"]}})

    img = save(driving_licence({**dl_ok, "dob": "1991-03-15",
                                "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"],
                                                    tamper_after={"dob": "1991-03-15"})}), "TST-024_signature_fail.jpg")
    case("TST-024", "Digital-signature failure: signed QR data altered after signing", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED", "FAIL"], "attention_required": True,
          "tampered": False, "expected_checks": {"digital_signature": ["FAIL"]}})

    img = save(driving_licence({**dl_ok, "number": "KA0520180076543", "name": "NIKHIL SYNTHETIC RAJ",
                                "qr": dl_qr_payload("KA0520180076543", "NIKHIL SYNTHETIC RAJ", dl_ok["dob"], dl_ok["expiry"])}),
               "TST-025_unregistered.jpg")
    case("TST-025", "Unregistered document: well-formed licence with no record in the mock registry", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["NOT_VERIFIED"], "attention_required": True,
          "tampered": False, "expected_checks": {"registry": ["NOT_VERIFIED"]}})

    img = save(make_passport(**{**base_pp, "issue": "2015-05-10", "expiry": "2025-05-09"}, bad_check="dob",
                             printed={"dob": "1997-04-12"}), "TST-026_multiple.jpg")
    case("TST-026", "Multiple simultaneous inconsistencies: expired + MRZ check digit + DOB mismatch", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["FAIL", "REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"document_validity": ["FAIL"], "mrz_check_digits": ["FAIL", "REVIEW_REQUIRED"]}})

    case("TST-027", "India–Nepal treaty national: Indian passport, no visa/stamp — must NOT be flagged", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "expected_checks": {"visa_requirement": ["NOT_APPLICABLE"], "stamp_requirement": ["NOT_APPLICABLE"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    case("TST-028", "India–Nepal third-country national without the required Nepal visa", [it_pp],
         {"document_types": ["FOREIGN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"visa_requirement": ["REVIEW_REQUIRED"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    case("TST-029", "India–Bhutan (post-2022 rules): Indian passport, no physical stamp — must NOT be flagged", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "expected_checks": {"stamp_requirement": ["NOT_APPLICABLE"], "visa_requirement": ["NOT_APPLICABLE"]}},
         border_route="INDIA_BHUTAN", direction="INDIA_TO_BHUTAN")

    # ---- additional conditions (nationality, damaged QR, missing MRZ/photo, live quality,
    #      stamp date, unexpected checkpoint, Indian/Bhutan markings, reference photo, cropping, visual signature)
    img = save(make_passport(**base_pp, nat="NPL", nat_text="NEPALI"), "TST-030_nationality_modified.jpg")
    case("TST-030", "Modified nationality: document says NEPALI, the (mock) registry record says INDIAN", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "expected_checks": {"registry": ["REVIEW_REQUIRED"]}})

    dmg = driving_licence({**dl_ok, "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"])})
    ImageDraw.Draw(dmg).rectangle((int(0.80 * 1100) + 40, int(0.68 * 700) + 20, int(0.80 * 1100) + 160, int(0.68 * 700) + 150),
                                  fill=(236, 244, 238))
    img = save(dmg, "TST-031_damaged_qr.jpg")
    case("TST-031", "Damaged/unreadable QR: part of the code is covered", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["NOT_VERIFIED", "REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False,
          "expected_checks": {"machine_readable_code": ["NOT_VERIFIED", "REVIEW_REQUIRED"]}})

    img = save(make_passport(**base_pp, no_mrz=True), "TST-032_missing_mrz.jpg")
    case("TST-032", "Missing MRZ on a passport data page", [img],
         {"document_types": ["INDIAN_PASSPORT", "DOCUMENT_TYPE_UNCERTAIN"], "expected_overall": ["NOT_VERIFIED", "REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False, "expected_checks": {"mrz_structure": ["NOT_VERIFIED", "REVIEW_REQUIRED"]}})

    img = save(driving_licence({**dl_ok, "no_photo": True,
                                "qr": dl_qr_payload(dl_ok["number"], dl_ok["name"], dl_ok["dob"], dl_ok["expiry"])}),
               "TST-033_missing_photo.jpg")
    case("TST-033", "Missing photo: licence with an empty photo area", [img],
         {"document_types": ["DRIVING_LICENCE"], "expected_overall": ["REVIEW_REQUIRED", "NOT_VERIFIED"],
          "attention_required": True, "tampered": False, "expected_checks": {"photo": ["REVIEW_REQUIRED", "NOT_VERIFIED"]}})

    poor_live = face(0, (400, 500), augment=True).filter(ImageFilter.GaussianBlur(9)).resize((90, 110))
    poor_live = Image.fromarray((np.asarray(poor_live).astype(np.float32) * 0.35).astype(np.uint8))
    live_poor = save(poor_live, "TST-034_live_low_quality.jpg", quality=40)
    case("TST-034", "Low-quality live face capture: blurred, dark, tiny — retake, not a mismatch", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["NOT_VERIFIED"], "attention_required": True,
          "tampered": False, "expected_checks": {"face_verification": ["NOT_VERIFIED"]}}, live_face=live_poor)

    early = stamp(["NEPAL IMMIGRATION", "KAKARBHITTA", "ARRIVAL", "12 AUG 2026"])
    page_early = save(stamp_page([(early, (260, 250))]), "TST-035_stamp_before_visa.jpg")
    case("TST-035", "Stamp date inconsistency: entry stamped before the visa's validity began", [it_pp, visa, page_early],
         {"document_types": ["FOREIGN_PASSPORT", "NEPAL_VISA", "IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False, "expected_checks": {"stamp_consistency": ["REVIEW_REQUIRED"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    odd = stamp(["NEPAL IMMIGRATION", "PASHUPATINAGAR", "ARRIVAL", "12 SEP 2026"])
    page_odd = save(stamp_page([(odd, (240, 250))]), "TST-036_unexpected_checkpoint.jpg")
    case("TST-036", "Unexpected checkpoint: foreigner stamped at a post not designated for foreigners", [it_pp, visa, page_odd],
         {"document_types": ["FOREIGN_PASSPORT", "NEPAL_VISA", "IMMIGRATION_STAMP"], "expected_overall": ["REVIEW_REQUIRED"],
          "attention_required": True, "tampered": False, "expected_checks": {"designated_crossing": ["REVIEW_REQUIRED"]}},
         border_route="INDIA_NEPAL", direction="INDIA_TO_NEPAL")

    ind = stamp(["BUREAU OF IMMIGRATION", "INDIA  RAXAUL", "ARRIVAL", "14 SEP 2026"])
    img = save(stamp_page([(ind, (260, 300))]), "TST-037_india_marking.jpg")
    case("TST-037", "Indian immigration marking (Raxaul) identified from text + checkpoint reference", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "stamp": {"country": "INDIA", "checkpoint": "RAXAUL"}, "expected_checks": {"checkpoint_match": ["PASS"]}})

    btn = stamp(["BHUTAN IMMIGRATION", "PHUENTSHOLING", "ENTRY", "15 SEP 2026"])
    img = save(stamp_page([(btn, (260, 300))]), "TST-038_bhutan_marking.jpg")
    case("TST-038", "Bhutan immigration marking (Phuentsholing) identified from text + checkpoint reference", [img],
         {"document_types": ["IMMIGRATION_STAMP"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "stamp": {"country": "BHUTAN", "checkpoint": "PHUENTSHOLING"}, "expected_checks": {"checkpoint_match": ["PASS"]}})

    ref_other = save(face(7, (400, 500)), "TST-039_reference_other_person.jpg")
    case("TST-039", "Live face matches the document, but the authorised reference photo shows someone else", [gen_pp],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["REVIEW_REQUIRED"], "attention_required": True,
          "tampered": False, "face_same": False, "expected_checks": {"face_verification": ["REVIEW_REQUIRED"]}},
         live_face=live_same, reference_face=ref_other)

    full = make_passport(**base_pp)
    img = save(full.crop((0, 0, int(full.width * 0.7), full.height)), "TST-040_cropped.jpg")
    case("TST-040", "Cropped document: right side and part of the MRZ outside the frame", [img],
         {"document_types": ["INDIAN_PASSPORT", "DOCUMENT_TYPE_UNCERTAIN", "FOREIGN_PASSPORT"],
          "expected_overall": ["NOT_VERIFIED", "REVIEW_REQUIRED"], "attention_required": True, "tampered": False})

    img = save(make_passport(**base_pp, signature=True), "TST-041_visual_signature.jpg")
    case("TST-041", "Visual signature only: an image of a signature is not treated as a digital signature", [img],
         {"document_types": ["INDIAN_PASSPORT"], "expected_overall": ["PASS"], "attention_required": False, "tampered": False,
          "expected_checks": {"mrz_check_digits": ["PASS"]}})
    return cases


def main() -> None:
    cases = build()
    (OUT / "ground_truth.json").write_text(json.dumps({
        "schema": "pramaan.synthetic_testset.v1", "data_classification": "SYNTHETIC_TEST_DATA",
        "travel_date": TRAVEL_DATE,
        "registry_seed": {"citizen_registry": [
            {"document_number": "Z1234567", "full_name": "ANANYA SYNTHETIC SHARMA", "date_of_birth": "12/04/1996",
             "nationality": "INDIAN", "gender": "F", "document_type": "PASSPORT", "date_of_expiry": "09/05/2031",
             "status": "ACTIVE"},
            {"document_number": "X1234567", "full_name": "ELENA SYNTHETIC ROSSI", "date_of_birth": "03/02/1990",
             "nationality": "ITALIAN", "gender": "F", "document_type": "PASSPORT", "date_of_expiry": "14/01/2030",
             "status": "ACTIVE"}]},
        "cases": cases}, indent=2) + "\n")
    print(f"{len(cases)} cases, {len(list(OUT.glob('*.jpg')))} images -> {OUT}")


if __name__ == "__main__":
    main()
