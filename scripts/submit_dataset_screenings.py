#!/usr/bin/env python3
"""
Submit every document in ID_DOCUMENT_DATASET as a real test screening
with the actual image uploaded as evidence.  Uses the real backend API
so results appear on both the Android app (via sync) and the web dashboard.
"""
import io
import sys
import time
from pathlib import Path

import requests
from PIL import Image

BASE_URL = "http://localhost:8000"
DATASET = Path("/home/bharti/ID_DOCUMENT_DATASET")

# ── Auth ──────────────────────────────────────────────────────────────────────

def login(username="officer1", password="BorderShield123") -> str:
    r = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]

# ── Helpers ───────────────────────────────────────────────────────────────────

OFFICERS = [
    "attari_officer", "petrapole_officer", "raxaul_officer",
    "jaigaon_officer", "phuentsholing_officer", "gelephu_officer",
    "samdrup_officer", "officer1",
]

def to_jpeg_bytes(path: Path) -> bytes:
    """Convert any image format (webp, png, jpeg) → JPEG bytes."""
    img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def crop_face_region(path: Path) -> bytes | None:
    """Crop a face-like region from a document image for use as selfie.
    Uses simple heuristics: for passport/ID cards, the face photo is
    typically in the left ~35% and top ~65% of the image."""
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        if w < 100 or h < 100:
            return None
        # Try upper-left quadrant (most ID cards have face there)
        face_crop = img.crop((0, int(h * 0.05), int(w * 0.4), int(h * 0.65)))
        # Resize to a reasonable selfie size
        face_crop = face_crop.resize((300, 400), Image.LANCZOS)
        buf = io.BytesIO()
        face_crop.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return None


def screen(token: str, doc_type: str, nationality: str, name: str,
           doc_number: str, dob: str | None = None, expiry: str | None = None,
           extra: dict | None = None) -> dict:
    ocr = {"name": name, "document_number": doc_number}
    if dob:
        ocr["date_of_birth"] = dob
    if expiry:
        ocr["date_of_expiry"] = expiry
    if extra:
        ocr.update(extra)
    payload = {
        "document_type": doc_type,
        "nationality": nationality,
        "ocr_fields": ocr,
        "ocr_confidence": 0.87,
    }
    r = requests.post(
        f"{BASE_URL}/documents/screen",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Screen failed {r.status_code}: {r.text[:200]}")
    return r.json()


def upload_image(token: str, verification_id: str, image_path: Path,
                 back_path: Path | None = None, has_face: bool = False) -> None:
    try:
        files = {"document_front": ("doc.jpg", to_jpeg_bytes(image_path), "image/jpeg")}
        if back_path and back_path.exists() and back_path.stat().st_size > 0:
            files["document_back"] = ("doc_back.jpg", to_jpeg_bytes(back_path), "image/jpeg")
        if has_face:
            face_bytes = crop_face_region(image_path)
            if face_bytes:
                files["selfie"] = ("selfie.jpg", face_bytes, "image/jpeg")
        r = requests.post(
            f"{BASE_URL}/images/{verification_id}/upload",
            files=files,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if r.status_code not in (200, 201):
            print(f"    ⚠ image upload {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"    ⚠ image upload error: {e}")


def submit_case(token: str, case_id: str) -> None:
    try:
        requests.post(
            f"{BASE_URL}/cases/{case_id}/submit",
            json={"note": None},
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
    except Exception:
        pass


# ── Document catalogue ────────────────────────────────────────────────────────
# Each entry: (label, doc_type, nationality, name, doc_number, dob, expiry,
#              image_path, back_path, extra_fields, has_face)

DOCS = [
    # ── INDIA PASSPORTS ───────────────────────────────────────────────────────
    (
        "India Passport — Garima Thapliyal (valid)",
        "passport", "IN", "Thaplival Garima", "SP003369",
        "01/07/1994", "03/09/2024",
        DATASET / "Indianpassportbiopage2025.jpg", None,
        {"mrz_line1": "P<INDTHAPLIYAL<<GARIMA<<<<<<<<<<<<<<<<<<<<<<<",
         "mrz_line2": "SP0033692IND9407012F3409221034028106959464124248",
         "gender": "F", "place_of_birth": "Coimbatore"},
        True,
    ),
    (
        "India Passport — Sita Maha Lakshmi (EXPIRED)",
        "passport", "IN", "Ramadugula Sita Maha Lakshmi", "J8369854",
        "23/09/1959", "10/10/2021",
        DATASET / "images (3).jpeg", None,
        {"mrz_line1": "P<INDRAMADUGULA<<SITA<MAHA<LAKSHMI<<<<<<<<<<",
         "mrz_line2": "J83698544IND5909234F2110101<<<<<<<<<<<<<<<<<<8",
         "gender": "F", "place_of_birth": "Gundugolanu", "place_of_issue": "Hyderabad"},
        True,
    ),

    # ── BHUTAN PASSPORTS ──────────────────────────────────────────────────────
    (
        "Bhutan Passport — Sonam Dema (valid)",
        "passport", "BT", "Sonam Dema", "G000000",
        "02/04/1991", "10/12/2027",
        DATASET / "images (11).jpeg", None,
        {"citizenship_id": "10701000736", "gender": "F",
         "place_of_birth": "Thimphu",
         "mrz_line1": "P<BTNDEMA<<SONAM<<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
         "mrz_line2": "G000000<<2BTN9104026F2712103107010007366<<<30"},
        True,
    ),
    (
        "Bhutan Passport — Sonam Younten (EXPIRED)",
        "passport", "BT", "Sonam Younten", "G030178",
        "14/03/1987", "27/04/2016",
        DATASET / "visa-requirement.jpeg", None,
        {"citizenship_id": "10503000118", "gender": "M",
         "place_of_birth": "Thimphu",
         "mrz_line1": "P<BTNYOUNTEN<<SONAM<<<<<<<<<<<<<<<<<<<<<<<<<<<",
         "mrz_line2": "G030178<<1BTN8703145M1604276105030000118<<<<36"},
        True,
    ),

    # ── INDIA VISAS ───────────────────────────────────────────────────────────
    (
        "India e-Visa ETA — Spanish tourist (EXPIRED)",
        "visa", "ES", "Traveler Spain", "ETA-ESP-2019-4756",
        None, "29/10/2019",
        DATASET / "01.jpg", None,
        {"visa_type": "e-Tourist", "issuing_country": "IN"},
        True,
    ),
    (
        "India Business Visa stamp — EXPIRED 2018",
        "visa", "IN", "Traveler Romania", "9013E3F81",
        None, "20/11/2018",
        DATASET / "02.jpg", None,
        {"visa_type": "Business", "issuing_country": "IN"},
        False,
    ),
    (
        "India Tourist Visa — AF713645 (BLACKLISTED)",
        "visa", "IN", "Demo India Visa Holder", "AF713645",
        None, "22/02/2009",
        DATASET / "05.jpg", None,
        {"visa_type": "Tourist", "issued_at": "Munich"},
        False,
    ),

    # ── NEPAL VISAS ───────────────────────────────────────────────────────────
    (
        "Nepal Visa On Arrival — T220281095 (EXPIRED)",
        "visa", "NP", "Demo Nepal Visa 2022", "T220281095",
        None, "24/10/2022",
        DATASET / "01_Nepal_Visa_On_Arrival.png", None,
        {"issuing_post": "TIA", "visa_plan": "MRE"},
        False,
    ),
    (
        "Nepal 15-Day Entry Visa — EXPIRED Dec 2020",
        "visa", "NP", "Traveler Nepal 2020", "NP-VIS-2020-001",
        None, "25/12/2020",
        DATASET / "02_Nepal_Entry_Visa.png", None,
        {"issuing_post": "TIA", "duration": "15 days"},
        False,
    ),
    (
        "Nepal Tourist Visa — T220078908 (EXPIRED Apr 2022)",
        "visa", "NP", "Traveler TIA April 2022", "T220078908",
        None, "25/04/2022",
        DATASET / "nepal-visa.jpg", None,
        {"issuing_post": "TIA", "visa_plan": "MRE"},
        False,
    ),
    (
        "Nepal Tourist Visa — T230070868 (EXPIRED May 2023)",
        "visa", "NP", "Traveler TIA Feb 2023", "T230070868",
        None, "16/05/2023",
        DATASET / "nepal-visa.jpg", None,
        {"issuing_post": "TIA", "duration": "90 days"},
        False,
    ),
    (
        "Nepal Tourist Visa — T246414719 (EXPIRED Nov 2024)",
        "visa", "NP", "Demo Nepal Visa Oct 2024", "T246414719",
        None, "09/11/2024",
        DATASET / "images (7).jpeg", None,
        {"passport_number": "YB3773974", "issuing_post": "TIA"},
        False,
    ),
    (
        "Nepal Tourist Visa — T24013 (EXPIRED Mar 2024)",
        "visa", "NP", "Demo Nepal Visa Mar 2024", "T24013",
        None, "30/03/2024",
        DATASET / "images (8).jpeg", None,
        {"issuing_post": "TIA", "duration": "30 days"},
        False,
    ),
    (
        "Nepal 15-Day Visa — Singapore issued 2018 (EXPIRED)",
        "visa", "SG", "M.M. Fatli", "NP-VIS-2018-SIN",
        None, "11/09/2018",
        DATASET / "images (9).jpeg", None,
        {"passport_number": "EE859995B", "issued_at": "Singapore"},
        False,
    ),
    (
        "Nepal Tourist Visa Washington DC — SUSPICIOUS (passport no 123456789)",
        "visa", "NP", "Traveler Washington DC 2007", "NP-VIS-2007-DC",
        None, "31/12/2007",
        DATASET / "Nepal-visa.jpg", None,
        {"passport_number": "123456789", "issued_at": "Washington DC"},
        False,
    ),

    # ── INDIA DRIVING LICENCES ────────────────────────────────────────────────
    (
        "India DL — Telangana — Upendram D Muthaiah",
        "driving_licence", "IN", "Upendram D Muthaiah", "TS00420140004496",
        None, "03/10/2029",
        DATASET / "dl_1.jpeg", None,
        {"state": "Telangana", "issued_on": "04/10/2019",
         "address": "HNO 7-1-83, Ricob Bazar, Khammam 507001"},
        True,
    ),
    (
        "India DL — Gujarat — Chetan Chauhan (EXPIRED)",
        "driving_licence", "IN", "Chetan Chauhan", "GJ0519940112841",
        "02/01/1974", "01/01/2024",
        DATASET / "dl_10.jpg", None,
        {"state": "Gujarat", "father_name": "Manharbhai",
         "address": "28 Parixit Society, Nr Jamna Nagar, Surat 395007"},
        True,
    ),
    (
        "India DL — Maharashtra — Suryakant Birajdar (EXPIRED)",
        "driving_licence", "IN", "Suryakant Birajdar", "MH1320070019358",
        "01/06/1977", "06/12/2016",
        DATASET / "dl_13.jpg", None,
        {"state": "Maharashtra", "address": "A/P Nimbargi, South Solapur"},
        True,
    ),
    (
        "India DL — Chhattisgarh — Kantlal Paikra (valid)",
        "driving_licence", "IN", "Kantlal Paikra", "CG1020170008007",
        "10/04/1987", "21/08/2037",
        DATASET / "dl_14.jpg", None,
        {"state": "Chhattisgarh", "issued_on": "22/08/2017",
         "father_name": "Ramphal Singh Paikra",
         "address": "Vill Bargawan Majhgawan, Dist Bilaspur C.G."},
        True,
    ),
    (
        "India DL — Tamil Nadu — Anuradha P (valid)",
        "driving_licence", "IN", "Anuradha P", "TN9920190000999",
        "13/12/1977", "12/12/2027",
        DATASET / "dl_18.jpg", None,
        {"state": "Tamil Nadu", "issued_on": "22/02/2019",
         "father_name": "Parthiban G"},
        True,
    ),
    (
        "India DL — Rajasthan old-style booklet (no details)",
        "driving_licence", "IN", "DL Holder Rajasthan", "RJ-OLD-1939-001",
        None, None,
        DATASET / "06.webp", None,
        {"state": "Rajasthan"},
        False,
    ),
    (
        "India DL — Kerala old-style (synthetic)",
        "driving_licence", "IN", "DL Holder Kerala", "KL-DL-SAMPLE-001",
        None, None,
        DATASET / "10.webp", None,
        {"state": "Kerala"},
        True,
    ),

    # ── BHUTAN DRIVING LICENCES ───────────────────────────────────────────────
    (
        "Bhutan DL — Amir Rai, Sarpang (valid)",
        "driving_licence", "BT", "Amir Rai", "G-18638",
        "25/04/2000", "19/08/2029",
        DATASET / "images (1).jpeg", None,
        {"cid": "11301001552", "district": "Sarpang"},
        True,
    ),
    (
        "Bhutan DL — Karma Dendup, Monggar (valid)",
        "driving_licence", "BT", "Karma Dendup", "T-6101",
        "01/01/1974", "06/01/2029",
        DATASET / "images (5).jpeg", None,
        {"cid": "10702001841", "district": "Monggar"},
        True,
    ),

    # ── BHUTAN NATIONAL ID (CID) ──────────────────────────────────────────────
    (
        "Bhutan Citizenship Card — Phuntsho Tashi (valid)",
        "national_id", "BT", "Phuntsho Tashi", "10712002883",
        "26/12/2000", None,
        DATASET / "images (6).jpeg", None,
        {"gender": "Male"},
        True,
    ),
    (
        "Bhutan Citizenship Card — Dawa Lhamo Sherpa (valid)",
        "national_id", "BT", "Dawa Lhamo Sherpa", "10701998042",
        "14/04/1998", None,
        DATASET / "images (10).jpeg", None,
        {"gender": "Female"},
        True,
    ),

    # ── NEPAL NATIONAL ID ─────────────────────────────────────────────────────
    (
        "Nepal NID — synthetic demo card",
        "national_id", "NP", "Nepal Citizen FEY1", "02200711",
        "20/01/2001", None,
        DATASET / "images.jpeg", None,
        {"citizenship_certificate": "22276922001"},
        True,
    ),
    (
        "Nepal Citizenship Certificate — Pushpa Kamal Dahal",
        "national_id", "NP", "Pushpa Kamal Dahal", "16378-256",
        "11/09/1954", None,
        DATASET / "images (4).jpeg", None,
        {"district": "Chitwan", "father_name": "Ghanshyam Dahal"},
        True,
    ),

    # ── NON-RESIDENT NEPALI ID — BLACKLISTED ──────────────────────────────────
    (
        "NRN Identity Card — KATH-B/1 (BLACKLISTED)",
        "national_id", "NP", "Dev Man Hirachan", "KATH-B/1",
        None, "10/02/2012",
        DATASET / "images (2).jpeg", None,
        {"country_of_residence": "Japan", "citizenship_no": "5467",
         "issuing_authority": "Ministry of Foreign Affairs Kathmandu"},
        True,
    ),
]


def run():
    # Login with all officers to get tokens for variety
    tokens = {}
    for officer in OFFICERS:
        try:
            tokens[officer] = login(officer)
        except Exception:
            pass
    if not tokens:
        print("ERROR: Could not login with any officer"); return
    officer_list = list(tokens.keys())
    print(f"Logged in with {len(officer_list)} officers: {', '.join(officer_list)}")
    print(f"Submitting {len(DOCS)} documents...\n")

    results = []
    for i, entry in enumerate(DOCS, 1):
        label, doc_type, nationality, name, doc_number, dob, expiry, img_path, back_path, extra, has_face = entry
        if extra is None:
            extra = {}

        if not img_path.exists() or img_path.stat().st_size < 100:
            print(f"[{i:02d}] SKIP (no image): {label}")
            continue

        officer = officer_list[i % len(officer_list)]
        token = tokens[officer]

        try:
            resp = screen(token, doc_type, nationality, name, doc_number, dob, expiry, extra)
            vid = resp["verification_id"]
            case_id = resp["case_id"]
            case_num = resp["case_number"]
            risk = resp["risk"]
            level = risk["level"]
            score = risk["score"]
            decision = risk["decision"]

            upload_image(token, vid, img_path, back_path, has_face=has_face)
            submit_case(token, case_id)

            flag = "🔴" if level == "HIGH_RISK" else "🟡" if level == "MEDIUM_RISK" else "🟢"
            print(f"[{i:02d}] {flag} {case_num}  {level} ({score})  {label}")
            print(f"      ↳ by {officer} — {risk['top_reason'][:70]}")
            results.append({"case_number": case_num, "label": label, "level": level, "score": score})
            time.sleep(0.3)

        except Exception as e:
            print(f"[{i:02d}] ERROR: {label} — {e}")

    print(f"\n{'='*70}")
    print(f"Done. {len(results)} cases created.")
    high = sum(1 for r in results if r["level"] == "HIGH_RISK")
    med  = sum(1 for r in results if r["level"] == "MEDIUM_RISK")
    low  = sum(1 for r in results if r["level"] == "LOW_RISK")
    print(f"  🔴 HIGH_RISK:   {high}")
    print(f"  🟡 MEDIUM_RISK: {med}")
    print(f"  🟢 LOW_RISK:    {low}")


if __name__ == "__main__":
    run()
