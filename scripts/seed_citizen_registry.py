"""Idempotent demo seeder for the mock citizen/passport registry (see
app/models/citizen_registry.py) — synthetic "this document number belongs
to this person" records, the positive counterpart to the watchlist-only
mock_central_registry. All data here is invented for this build; nothing
is a real person or a real government record (see CLAUDE.md). Skips any
document_number that already exists rather than erroring or duplicating.

Two entries are deliberately aligned with app/api/routes/testing.py's
synthetic scenario generator (same passport numbers/names/DOB it uses by
default) so the "genuine_passport" test scenario produces a real MATCH
and "possible_impersonation" produces a real MISMATCH, instead of every
demo run landing on NO_RECORD.

Usage (from project root):
    python -m scripts.seed_citizen_registry
"""
from app.db.session import SessionLocal
from app.repositories.citizen_registry_repository import find_by_document_number, insert_entry

# (document_number, full_name, date_of_birth, nationality, gender, document_type, date_of_expiry, status)
DEMO_ENTRIES = [
    # Aligned with tests/synthetic_documents.py's generate_mrz_lines() defaults
    # and app/api/routes/testing.py's TestScenario.GENUINE_PASSPORT — a real,
    # deliberate MATCH for that scenario.
    ("N1234567", "JOHN MICHAEL SMITH", "12/04/1990", "INDIAN", "M", "passport", "11/04/2030", "ACTIVE"),
    # Aligned with TestScenario.MULTIPLE_IDENTITIES's document number
    # (app/api/routes/testing.py uses "N7654321" with declared name "JANE
    # DOE") but registered here under a different real name — a
    # deliberate MISMATCH demo case.
    ("N7654321", "PRIYA RAMESH NAIR", "23/08/1988", "INDIAN", "F", "passport", "22/08/2028", "ACTIVE"),
    ("M9988776", "AMIT KUMAR SHARMA", "05/11/1985", "INDIAN", "M", "passport", "04/11/2029", "ACTIVE"),
    ("M5544332", "SUNITA DEVI YADAV", "17/02/1992", "INDIAN", "F", "passport", "16/02/2027", "ACTIVE"),
    ("K1122334", "RAJESH SINGH RATHORE", "30/06/1979", "INDIAN", "M", "passport", "29/06/2024", "EXPIRED"),
    ("K7788990", "ANJALI PATEL MEHTA", "09/09/1995", "INDIAN", "F", "passport", "08/09/2031", "ACTIVE"),
    ("L2233445", "VIKRAM SINGH CHAUHAN", "14/01/1983", "INDIAN", "M", "passport", "13/01/2028", "ACTIVE"),
    ("L6677889", "DEEPIKA RANI VERMA", "21/12/1991", "INDIAN", "F", "passport", "20/12/2026", "ACTIVE"),
    ("J3344556", "SURESH CHANDRA GUPTA", "03/03/1975", "INDIAN", "M", "passport", "02/03/2025", "REVOKED"),
    ("J8899001", "KAVITA SHARMA JOSHI", "27/07/1989", "INDIAN", "F", "passport", "26/07/2029", "ACTIVE"),
    ("NP112233", "BIKRAM THAPA MAGAR", "11/05/1987", "NEPALI", "M", "passport", "10/05/2027", "ACTIVE"),
    ("NP445566", "SITA KUMARI GURUNG", "19/10/1993", "NEPALI", "F", "passport", "18/10/2028", "ACTIVE"),
    ("NP778899", "RAM BAHADUR TAMANG", "02/02/1981", "NEPALI", "M", "passport", "01/02/2026", "ACTIVE"),
    ("BT100200", "TASHI WANGCHUK DORJI", "25/04/1990", "BHUTANESE", "M", "passport", "24/04/2030", "ACTIVE"),
    ("BT300400", "PEMA YANGZOM CHODEN", "16/08/1994", "BHUTANESE", "F", "passport", "15/08/2029", "ACTIVE"),
    ("H5566778", "ARUN PRAKASH TIWARI", "08/01/1986", "INDIAN", "M", "national_id", None, "ACTIVE"),
    ("H9900112", "MEERA LAKSHMI IYER", "12/06/1997", "INDIAN", "F", "national_id", None, "ACTIVE"),
    ("G3344990", "SANJAY DUTT BHATIA", "29/09/1978", "INDIAN", "M", "driving_licence", "28/09/2033", "ACTIVE"),
    ("G6677001", "POOJA AGARWAL SAXENA", "04/04/1996", "INDIAN", "F", "driving_licence", "03/04/2036", "ACTIVE"),
    ("F1122998", "MOHAN LAL PRAJAPATI", "22/11/1982", "INDIAN", "M", "permit", "21/11/2025", "ACTIVE"),
]


def seed_citizen_registry() -> None:
    db = SessionLocal()
    try:
        for document_number, full_name, dob, nationality, gender, doc_type, expiry, status in DEMO_ENTRIES:
            if find_by_document_number(db, document_number) is not None:
                print(f"Citizen registry entry '{document_number}' already exists; skipping.")
                continue
            insert_entry(
                db,
                document_number=document_number,
                full_name=full_name,
                date_of_birth=dob,
                nationality=nationality,
                document_type=doc_type,
                date_of_expiry=expiry,
                gender=gender,
                status=status,
            )
            print(f"Created citizen registry entry '{document_number}' ({full_name}).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_citizen_registry()
