"""Unit tests for the modular document-verification services (no OCR model
needed — these run in milliseconds)."""
from datetime import date

import numpy as np
import pytest

from app.services.docverify import border_rules, decision, reference, registries, signatures
from app.services.docverify.consistency import compare_values
from app.services.docverify.forensics import find_duplicates
from app.services.docverify.mrz import parse_mrz
from app.services.docverify.security_features import detect_yellow_gold_feature
from app.services.docverify.stamps import identify_stamp
from app.services.docverify.types import (CheckResult, CheckStatus, DocumentAnalysis, DocumentType,
                                          DocumentTypeResult, FieldValue, Region, RegionLabel)
from app.services.validation.mrz import MRZFormatError, compute_check_digit

S = CheckStatus


def _td3(number="Z1234567", dob="960412", expiry="310509", nat="IND", bad_dob=False):
    num = number.ljust(9, "<")
    cn, cd, ce = compute_check_digit(num), compute_check_digit(dob), compute_check_digit(expiry)
    if bad_dob:
        cd = (cd + 3) % 10
    pers = "<" * 14 + "<"
    comp = compute_check_digit(f"{num}{cn}{dob}{cd}{expiry}{ce}{pers}")
    return ["P<INDSHARMA<<ANANYA<SYNTHETIC".ljust(44, "<"), f"{num}{cn}{nat}{dob}{cd}F{expiry}{ce}{pers}{comp}"]


# ------------------------------------------------------------------ MRZ

def test_td3_valid_and_dates():
    r = parse_mrz(_td3())
    assert r["format"] == "TD3" and r["all_checks_valid"]
    assert r["date_of_birth_iso"] == "1996-04-12" and r["date_of_expiry_iso"] == "2031-05-09"
    assert r["full_name"] == "ANANYA SYNTHETIC SHARMA"


def test_td3_ocr_confusions_are_corrected_by_field_class():
    l1, l2 = _td3()
    noisy = [l1.replace("IND", "1ND").replace("SYNTHETIC", "SYNTHET1C"), l2.replace("IND", "1ND").replace("9604124", "96O4124")]
    r = parse_mrz(noisy)
    assert r["all_checks_valid"] and r["issuing_country"] == "IND" and r["nationality"] == "IND"
    assert r["ocr_corrections"], "corrections must be reported, never hidden"


def test_td3_check_digit_failure_is_reported():
    r = parse_mrz(_td3(bad_dob=True))
    assert not r["all_checks_valid"] and "date_of_birth" in r["failed_checks"]


def test_mrv_a_visa():
    num = "T26004411".ljust(9, "<")
    l2 = f"{num}{compute_check_digit(num)}ITA900203{compute_check_digit('900203')}F261129{compute_check_digit('261129')}" + "<" * 16
    r = parse_mrz(["V<NPLROSSI<<ELENA".ljust(44, "<"), l2])
    assert r["format"] == "MRV-A" and r["all_checks_valid"] and r["document_code"] == "V"


def test_malformed_mrz_is_a_format_error_not_padded_away():
    with pytest.raises(MRZFormatError):
        parse_mrz(["P<INDSHARMA<<ANANYA", "Z1234567<1IND9604124F"])


# ------------------------------------------------------------------ consistency

@pytest.mark.parametrize("a,b,expected", [
    ("ANANYASYNTHETIC SHARMA", "ANANYA SYNTHETIC SHARMA", "CONSISTENT"),
    ("SHARMA ANANYA", "ANANYA SHARMA", "CONSISTENT"),
    ("VERMA ANANYA", "SHARMA ANANYA", "PARTIAL_MATCH"),
    ("RAHUL DAS", "PRIYA KUMARI", "INCONSISTENCY_DETECTED"),
])
def test_name_comparison(a, b, expected):
    assert compare_values("name", a, b) == expected


def test_number_comparison_flags_ocr_confusion_separately():
    assert compare_values("document_number", "Z1234567", "Z1234567") == "CONSISTENT"
    assert compare_values("document_number", "Z12345O7", "Z1234507") == "POSSIBLE_OCR_CONFUSION"
    assert compare_values("document_number", "Z1234567", "Z1234568") == "INCONSISTENCY_DETECTED"


# ------------------------------------------------------------------ reference + stamps

def test_checkpoint_reference_matching():
    m = reference.match_checkpoint("NEPAL IMMIGRATION KAKARVITTA ARRIVAL")
    assert m and m["record"]["checkpoint_id"] == "NP-KAKARBHITTA" and m["record"]["checkpoint_type"] == "LAND_BORDER"
    assert reference.match_checkpoint("SYNTHETIC CONSULATE ISSUED AT") is None  # no fuzzy false positive


def test_every_checkpoint_cites_a_source():
    for cp in reference.all_checkpoints():
        assert cp["reference_source"] and all(s["url"].startswith("https://") for s in cp["reference_source"])


def _region():
    return Region(id="s1", label=RegionLabel.STAMP, bbox=[0, 0, 100, 60], confidence=0.9, source="test")


def test_stamp_identified_from_text_not_shape():
    s = identify_stamp("NEPAL IMMIGRATION KAKARBHITTA ARRIVAL 12 SEP 2026", _region(), 0.95)
    assert s.stamp_type.value == "ENTRY_STAMP" and s.identification == "IDENTIFIED"
    assert s.country == "NEPAL" and s.checkpoint == "KAKARBHITTA" and s.date == "2026-09-12"


def test_stamp_missing_information_is_partial_not_invented():
    s = identify_stamp("NEPAL IMMIGRATION ARRIVAL", _region(), 0.8)
    assert s.identification == "PARTIALLY_IDENTIFIED" and "checkpoint" in s.missing_fields and s.checkpoint is None


def test_stamp_country_checkpoint_conflict_is_noted():
    s = identify_stamp("NEPAL IMMIGRATION JAIGAON ARRIVAL 05 SEP 2026", _region(), 0.9)
    assert any("belongs to INDIA" in n for n in s.notes)


def test_printed_heading_is_not_a_stamp():
    assert identify_stamp("GOVERNMENT OF NEPAL TOURIST VISA", Region(
        id="x", label=RegionLabel.STAMP, bbox=[0, 0, 10, 10], confidence=0.5, source="classical:ink-segmentation"), 0.9) is None


# ------------------------------------------------------------------ border rules

def _doc(dt, fields=None, mrz_nat=None):
    return DocumentAnalysis(document_index=0, document_type=DocumentTypeResult(document_type=dt, country=None, confidence=0.9),
                            fields={k: FieldValue(value=v, confidence=0.9, source="ocr") for k, v in (fields or {}).items()},
                            mrz={"nationality": mrz_nat, "all_checks_valid": True} if mrz_nat else None)


def test_treaty_national_without_visa_is_not_flagged():
    checks, info = border_rules.evaluate("INDIA_NEPAL", [_doc(DocumentType.INDIAN_PASSPORT, mrz_nat="IND")],
                                         on=date(2026, 9, 23), direction="INDIA_TO_NEPAL", declared_nationality=None)
    by = {c.name: c.status for c in checks}
    assert by["visa_requirement"] == S.NOT_APPLICABLE and by["stamp_requirement"] == S.NOT_APPLICABLE


def test_third_country_without_visa_goes_to_review_not_fail():
    checks, _ = border_rules.evaluate("INDIA_NEPAL", [_doc(DocumentType.FOREIGN_PASSPORT, mrz_nat="ITA")],
                                      on=date(2026, 9, 23), direction="INDIA_TO_NEPAL", declared_nationality=None)
    by = {c.name: c.status for c in checks}
    assert by["visa_requirement"] == S.REVIEW_REQUIRED and S.FAIL not in by.values()


def test_aadhaar_not_accepted_for_adults_but_advisory_only():
    checks, _ = border_rules.evaluate("INDIA_NEPAL", [_doc(DocumentType.AADHAAR, {"date_of_birth": "1990-01-01"})],
                                      on=date(2026, 9, 23), direction=None, declared_nationality=None)
    c = next(c for c in checks if c.name == "accepted_travel_document")
    assert c.status == S.REVIEW_REQUIRED and not c.blocking


def test_bhutan_rules_are_date_aware():
    assert reference.rule_version_for("INDIA_BHUTAN", date(2021, 1, 1))["version"] == "pre-2022-09-23"
    assert reference.rule_version_for("INDIA_BHUTAN", date(2026, 9, 23))["version"] == "2022-09-23-onward"


# ------------------------------------------------------------------ decision engine

def _c(name, status, strong=False, blocking=True):
    return CheckResult(name=name, status=status, summary=name, strong_evidence=strong, blocking=blocking)


def test_single_strong_failure_is_review_not_fail():
    assert decision.overall_status([_c("document_validity", S.FAIL, strong=True), _c("ocr", S.PASS)]) == S.REVIEW_REQUIRED


def test_two_independent_strong_failures_fail():
    checks = [_c("document_validity", S.FAIL, strong=True), _c("mrz_check_digits", S.FAIL, strong=True)]
    assert decision.overall_status(checks) == S.FAIL


def test_advisory_does_not_change_status_and_registry_absence_is_its_own_status():
    assert decision.overall_status([_c("ocr", S.PASS), _c("layout", S.REVIEW_REQUIRED, blocking=False)]) == S.PASS
    assert decision.overall_status([_c("ocr", S.PASS), _c("registry", S.REGISTRY_NOT_AVAILABLE)]) == S.REGISTRY_NOT_AVAILABLE


def test_risk_score_is_explained():
    score, level, parts = decision.risk([_c("mrz_consistency", S.REVIEW_REQUIRED, strong=True)])
    assert score == 20 and level == "LOW" and parts[0]["reason"]


# ------------------------------------------------------------------ signatures / registries

def test_signed_payload_verifies_and_tampering_breaks_it():
    import json
    raw = signatures.sign_synthetic({"dl_no": "MH1220190012345", "dob": "1994-03-15"})
    assert signatures.verify_signed_payload(raw, date(2026, 9, 23))["status"] == "PASS"
    env = json.loads(raw)
    env["payload"]["dob"] = "1991-03-15"
    bad = signatures.verify_signed_payload(json.dumps(env), date(2026, 9, 23))
    assert bad["status"] == "FAIL" and bad["document_integrity"] == "MODIFIED_AFTER_SIGNING_OR_WRONG_KEY"


def test_unknown_signer_is_not_verified_not_fail():
    import json
    env = json.loads(signatures.sign_synthetic({"a": 1}))
    env["kid"] = "SOMEONE-ELSE"
    assert signatures.verify_signed_payload(json.dumps(env), date(2026, 9, 23))["status"] == "NOT_VERIFIED"


def test_dl_registry_modes():
    assert registries.DrivingLicenceRegistry(mode="mock").verify_driving_licence("MH1220190012345")["status"] == "VALID"
    assert registries.DrivingLicenceRegistry(mode="mock").verify_driving_licence("KA0520180076543")["status"] == "NO_RECORD"
    assert registries.DrivingLicenceRegistry(mode="disabled").verify_driving_licence("X")["status"] == "REGISTRY_NOT_AVAILABLE"
    assert registries.DrivingLicenceRegistry(mode="mock", offline=True).verify_driving_licence("X")["status"] == "REGISTRY_NOT_AVAILABLE"


def test_aadhaar_is_always_routed_to_official_verification():
    assert registries.AadhaarOfficialVerifier().verify(True)["status"] == "OFFICIAL_VERIFICATION_REQUIRED"


# ------------------------------------------------------------------ pixels (no OCR)

def _card(with_gold: bool) -> np.ndarray:
    import cv2
    img = np.full((700, 1100, 3), (238, 244, 236), np.uint8)
    if with_gold:
        cv2.rectangle(img, (55, 224), (198, 371), (55, 175, 212), -1)  # BGR gold
        for y in (260, 297, 334):
            cv2.line(img, (63, y), (190, y), (30, 120, 150), 2)
        cv2.line(img, (126, 232), (126, 363), (30, 120, 150), 2)
    return img


def test_yellow_gold_visual_feature_detected_and_template_consistent():
    r = detect_yellow_gold_feature(_card(True), [0.04, 0.30, 0.20, 0.56])
    assert r["detected"] and r["feature_type"] == "VISUAL_SECURITY_FEATURE"
    assert r["position_consistency"] == "PASS" and r["template_consistency"] == "PASS"
    assert len(r["bbox"]) == 4 and r["is_electronic_chip"] == "UNKNOWN_NOT_ASSESSED"


def test_missing_yellow_gold_feature_is_not_verified_not_fake():
    r = detect_yellow_gold_feature(_card(False), [0.04, 0.30, 0.20, 0.56])
    assert not r["detected"] and "reliably" in r["reason"]


def test_duplicated_region_is_found():
    rng = np.random.default_rng(0)
    gray = (rng.random((600, 600)) * 255).astype(np.uint8)
    gray[400:500, 350:470] = gray[50:150, 50:170]
    hits = find_duplicates(gray, [("stamp", [50, 50, 170, 150])])
    assert hits and hits[0]["indicator"] == "duplicated_image_region"


# ------------------------------------------------------------------ checklist additions

def test_glare_is_found_on_specular_highlight_but_not_on_white_paper():
    from app.services.docverify.pipeline import _glare_fraction

    paper = np.full((600, 900), 245, np.uint8)
    assert _glare_fraction(paper) == 0.0
    card = np.full((600, 900), 170, np.uint8)
    card[200:260, 300:420] = 255  # specular blob on a mid-tone card
    assert _glare_fraction(card) > 0.004


def test_dataset_registry_detects_conflicting_records(db_session):
    from app.models.document_verification import DatasetRegistryRecord

    assert registries.lookup_dataset_registry(db_session, "PA0319064") is None  # empty table -> behaves as before
    for i, name in enumerate(["RESHAM KUMAR", "RESHAM KUMAR"]):
        db_session.add(DatasetRegistryRecord(source_file=f"f{i}", source_sha256=f"s{i}", document_type="FOREIGN_PASSPORT",
                                             document_number="PA0319064", full_name=name, record_status="MRZ_VALIDATED"))
    db_session.commit()
    assert registries.lookup_dataset_registry(db_session, "PA 0319064")["status"] == "FOUND"
    db_session.add(DatasetRegistryRecord(source_file="f9", source_sha256="s9", document_type="FOREIGN_PASSPORT",
                                         document_number="PA0319064", full_name="SOMEONE ELSE", record_status="OCR_UNREVIEWED"))
    db_session.commit()
    assert registries.lookup_dataset_registry(db_session, "PA0319064")["status"] == "CONFLICT"
    assert registries.lookup_dataset_registry(db_session, "PA0319064", offline=True) is None  # never "checked" offline


def test_invalid_mrz_country_code_is_flagged():
    from app.services.docverify.pipeline import Ctx, _capture_checks

    num, dob, exp = "Z1234567<", "960412", "310509"
    pers = "<" * 15
    comp = compute_check_digit(f"{num}{compute_check_digit(num)}{dob}{compute_check_digit(dob)}{exp}{compute_check_digit(exp)}{pers}")
    mrz = parse_mrz(["P<QQQSHARMA<<ANANYA".ljust(44, "<"),
                     f"{num}{compute_check_digit(num)}QQQ{dob}{compute_check_digit(dob)}F{exp}{compute_check_digit(exp)}{pers}{comp}"])
    doc = DocumentAnalysis(document_index=0, document_type=DocumentTypeResult(document_type=DocumentType.FOREIGN_PASSPORT,
                                                                              country=None, confidence=0.9), mrz=mrz)
    ctx = Ctx(on=date(2026, 9, 23))
    _capture_checks(ctx, doc)
    c = next(c for c in ctx.checks if c.name == "nationality_code")
    assert c.status == S.REVIEW_REQUIRED and "QQQ" in c.summary


def test_live_capture_with_two_faces_asks_for_a_retake():
    import io
    from PIL import Image
    from app.services.docverify.pipeline import Ctx, _live_capture_checks
    from scripts.docverify.synthetic_faces import synthetic_face

    canvas = Image.new("RGB", (640, 380), "white")
    canvas.paste(synthetic_face(1), (10, 0))
    canvas.paste(synthetic_face(2), (330, 0))
    buf = io.BytesIO()
    canvas.save(buf, "PNG")
    ctx = Ctx(on=date(2026, 9, 23))
    assert _live_capture_checks(ctx, 0, buf.getvalue()) is False
    c = next(c for c in ctx.checks if c.name == "face_verification")
    assert c.status == S.NOT_VERIFIED and "retake" in c.summary.lower()


def test_sideways_document_is_rotated_before_reading():
    import io
    from app.services.docverify.pipeline import analyze_image
    from scripts.docverify.generate_synthetic_testset import driving_licence

    img = driving_licence(dict(face=2, number="MH1220190012345", name="ARJUN SYNTHETIC MEHTA", dob="1994-03-15",
                               issue="2019-06-10", expiry="2039-03-14", qr=None)).rotate(90, expand=True)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    doc, _, _ = analyze_image(buf.getvalue(), 0, on=date(2026, 9, 23))
    assert doc.quality.get("rotation_corrected_degrees") in (90, 270)
    assert doc.document_type.document_type == DocumentType.DRIVING_LICENCE


def test_two_portraits_are_a_normal_layout_three_are_flagged():
    """Passports/visas/ID cards print a secondary ("ghost") portrait: two
    photographs are compared, not flagged; three matches no standard layout."""
    import numpy as np

    from app.services.docverify.photo import assess_photo
    from app.services.docverify.types import Region, RegionLabel

    img = np.full((700, 1100, 3), 230, np.uint8)
    main = Region(id="p1", label=RegionLabel.PHOTOGRAPH, bbox=[40, 120, 320, 480], confidence=0.9, source="t")
    ghost = Region(id="p2", label=RegionLabel.PHOTOGRAPH, bbox=[800, 300, 1000, 540], confidence=0.9, source="t")
    third = Region(id="p3", label=RegionLabel.PHOTOGRAPH, bbox=[420, 300, 640, 560], confidence=0.9, source="t")
    two = assess_photo(img, [main, ghost], None)
    assert not any(s["signal"] == "multiple_faces" for s in two["signals"])
    assert two["secondary_region"] == ghost.bbox and two["bbox"] == main.bbox
    three = assess_photo(img, [main, ghost, third], None)
    assert any(s["signal"] == "multiple_faces" for s in three["signals"])
