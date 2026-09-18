import json
import shutil

import pytest

from app.services.validation.cross_check import cross_validate
from app.services.validation.engine import DefaultValidationEngine
from app.services.validation.mrz import MRZFormatError, compute_check_digit, parse_td3
from app.services.validation.verhoeff import compute_verhoeff_checksum, validate_verhoeff
from tests.synthetic_documents import (
    generate_mrz_lines,
    generate_passport_back_image,
    generate_passport_image,
)

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


# ---- MRZ checksum (pure algorithm) ----------------------------------------


def test_mrz_check_digit_known_icao_example():
    # Official ICAO 9303 worked example: passport number field "L898902C3"
    # (padded to 9 with '<': "L898902C3") has check digit 6.
    assert compute_check_digit("L898902C3") == 6


def test_mrz_parses_valid_generated_mrz():
    line1, line2 = generate_mrz_lines()
    result = parse_td3(line1, line2)
    assert result.all_checks_valid
    assert result.composite_valid
    assert result.surname == "SMITH"
    assert result.given_names == "JOHN MICHAEL"
    assert result.passport_number == "N1234567"
    assert result.date_of_birth == "900412"


def test_mrz_detects_corrupted_check_digit():
    line1, line2 = generate_mrz_lines()
    # Flip the passport-number check digit (position 9) to something wrong.
    corrupted_digit = "0" if line2[9] != "0" else "1"
    corrupted_line2 = line2[:9] + corrupted_digit + line2[10:]
    result = parse_td3(line1, corrupted_line2)
    assert not result.all_checks_valid
    passport_check = next(c for c in result.check_digits if c.field == "passport_number")
    assert not passport_check.valid


def test_mrz_rejects_malformed_line():
    with pytest.raises(MRZFormatError):
        parse_td3("too short", "also too short")


# ---- Verhoeff / Aadhaar checksum (pure algorithm) --------------------------


def test_verhoeff_round_trip_valid():
    base = "123456789012"[:11]
    check_digit = compute_verhoeff_checksum(base)
    full_number = base + str(check_digit)
    assert validate_verhoeff(full_number)


def test_verhoeff_detects_corrupted_digit():
    base = "123456789012"[:11]
    check_digit = compute_verhoeff_checksum(base)
    full_number = base + str(check_digit)
    corrupted = full_number[:-1] + ("0" if full_number[-1] != "0" else "1")
    assert not validate_verhoeff(corrupted)


def test_verhoeff_known_wikipedia_example():
    # Wikipedia's worked example: base digits "236" -> check digit 3,
    # giving the valid Verhoeff number "2363".
    assert compute_verhoeff_checksum("236") == 3
    assert validate_verhoeff("2363")


# ---- Front/back cross-validation -------------------------------------------


def test_cross_validate_matching_fields():
    line1, line2 = generate_mrz_lines()
    mrz = parse_td3(line1, line2)
    front_fields = {
        "name": "JOHN MICHAEL SMITH",
        "passport_number": "N1234567",
        "nationality": "INDIAN",
        "date_of_birth": "12/04/1990",
        "date_of_expiry": "11/04/2030",
    }
    findings = cross_validate(front_fields, mrz)
    assert all(f.status == "PASS" for f in findings)


def test_cross_validate_flags_mismatched_document_number():
    line1, line2 = generate_mrz_lines()
    mrz = parse_td3(line1, line2)
    front_fields = {"passport_number": "X9999999"}
    findings = cross_validate(front_fields, mrz)
    number_finding = next(f for f in findings if f.check == "cross_check_document_number")
    assert number_finding.status == "FAIL"
    assert "X9999999" in number_finding.reason
    assert "N1234567" in number_finding.reason


# ---- Engine fusion ----------------------------------------------------------


def test_engine_verhoeff_path_for_indian_national():
    engine = DefaultValidationEngine()
    base = "99999999999"  # 11 digits + 1 check digit = 12-digit Aadhaar format
    check_digit = compute_verhoeff_checksum(base)
    aadhaar = base + str(check_digit)
    result = engine.validate(
        ocr_result={"date_of_expiry": "01/01/2099"},
        nationality="INDIAN",
        aadhaar_number=aadhaar,
    )
    checksum_finding = next(f for f in result.findings if f.check == "aadhaar_checksum")
    assert checksum_finding.status == "PASS"


def test_engine_flags_expired_document():
    engine = DefaultValidationEngine()
    result = engine.validate(ocr_result={"date_of_expiry": "01/01/2000"})
    expiry_finding = next(f for f in result.findings if f.check == "expiry")
    assert expiry_finding.status == "FAIL"
    assert result.status == "FAIL"


# ---- Endpoint integration (real OCR of a synthetic MRZ image) -------------

pytestmark_ocr = pytest.mark.skipif(
    not TESSERACT_AVAILABLE, reason="tesseract binary not installed on this host"
)


def _login(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username="validationtester", hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()

    response = client.post("/auth/login", json={"username": "validationtester", "password": "Str0ngPass!"})
    assert response.status_code == 200
    return response.json()["access_token"]


@pytestmark_ocr
def test_validate_endpoint_cross_checks_real_mrz_ocr(client, db_session):
    token = _login(client, db_session)
    line1, line2 = generate_mrz_lines()
    back_image_bytes = generate_passport_back_image(line1, line2)

    front_fields = {
        "name": "JOHN MICHAEL SMITH",
        "passport_number": "N1234567",
        "nationality": "INDIAN",
        "date_of_birth": "12/04/1990",
        "date_of_expiry": "11/04/2030",
    }

    response = client.post(
        "/documents/validate",
        headers={"Authorization": f"Bearer {token}"},
        data={"nationality": "INDIAN", "front_fields": json.dumps(front_fields)},
        files={"back_image": ("back.png", back_image_bytes, "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    checks = {f["check"]: f for f in body["findings"]}
    assert "mrz_checksum_composite" in checks
    assert checks["mrz_checksum_composite"]["status"] == "PASS"
    assert checks["cross_check_document_number"]["status"] == "PASS"


def test_validate_endpoint_requires_auth(client):
    response = client.post(
        "/documents/validate",
        data={"nationality": "INDIAN", "front_fields": "{}"},
    )
    assert response.status_code == 401
