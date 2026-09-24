"""Electronic documents are recognised and routed to the issuing service —
never reported as confirmed by it."""
import pytest

from app.services.docverify.electronic import detect
from app.services.docverify.types import DocumentType as D


@pytest.mark.parametrize("text,dtype,form", [
    ("INDIAN e-VISA Electronic Travel Authorization (ETA) ETA Number : X", D.INDIAN_VISA, "E_VISA"),
    ("Unique Identification Authority of India e-Aadhaar  Download Date: 01/01/2026", D.AADHAAR, "E_AADHAAR"),
    ("Issued by DigiLocker  Driving Licence  mParivahan", D.DRIVING_LICENCE, "E_DRIVING_LICENCE"),
    ("Online Entry Permit  Permit No 123", D.BHUTAN_ENTRY_PERMIT, "E_PERMIT"),
])
def test_recognised(text, dtype, form):
    e = detect(text, dtype)
    assert e and e["form"] == form and e["official_check"]
    assert "verified" not in e["label"].lower()


def test_physical_documents_are_not_electronic():
    assert detect("UNION OF INDIA DRIVING LICENCE  DL No MH12 20110012345", D.DRIVING_LICENCE) is None
    assert detect("REPUBLIC OF INDIA PASSPORT P<IND", D.INDIAN_PASSPORT) is None


def test_marker_needs_matching_document_type():
    # "ETA" wording on a passport page is not an e-Visa
    assert detect("ETA NUMBER 12345", D.INDIAN_PASSPORT) is None
