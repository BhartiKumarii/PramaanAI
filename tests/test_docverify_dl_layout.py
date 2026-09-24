"""Indian Union driving licence layout: values printed above their labels,
3-digit RTO codes, two dates under two labels. Synthetic lines only."""
from app.services.docverify.fields import extract_fields
from app.services.docverify.types import DocumentType, OcrLine


def L(text, x0, y0, x1, y1):
    return OcrLine(text=text, confidence=0.97, bbox=[x0, y0, x1, y1])


def test_name_and_relation_printed_above_their_labels():
    lines = [L("RAM KUMAR VERMA", 294, 383, 585, 416), L("Name:", 31, 409, 119, 441),
             L("Date of Birth:15-01-1963", 30, 430, 360, 488),
             L("SITA RAM", 387, 475, 578, 505), L("Son/Daughter/Wife of:", 33, 487, 323, 528)]
    f = extract_fields(lines, DocumentType.DRIVING_LICENCE)
    assert f["name"].value == "RAM KUMAR VERMA"
    assert f["relation_name"].value == "SITA RAM"
    assert f["date_of_birth"].value == "1963-01-15"


def test_issue_and_validity_dates_under_their_labels():
    lines = [L("Issue Date", 284, 223, 419, 254), L("Validity(NT)", 449, 216, 610, 251),
             L("06-05-2025", 291, 247, 445, 283), L("05-05-2030", 460, 247, 613, 283)]
    f = extract_fields(lines, DocumentType.DRIVING_LICENCE)
    assert f["date_of_issue"].value == "2025-05-06"
    assert f["date_of_expiry"].value == "2030-05-05"


def test_three_digit_rto_code():
    f = extract_fields([L("INDIAN UNION DRIVING LICENCE", 0, 0, 400, 30), L("TS00420140004496", 350, 157, 600, 190)],
                       DocumentType.DRIVING_LICENCE)
    assert f["document_number"].value == "TS00420140004496"
