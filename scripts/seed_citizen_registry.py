"""Idempotent demo seeder for the mock citizen/passport registry.
All entries are synthetic or from publicly available sample documents —
explicitly labelled mock data; nothing here is a real government record.

Usage:
    python -m scripts.seed_citizen_registry
"""
from app.db.session import SessionLocal
from app.repositories.citizen_registry_repository import find_by_document_number, insert_entry

# (document_number, full_name, date_of_birth, nationality, gender,
#  document_type, date_of_expiry, status)
DEMO_ENTRIES = [
    # ── Aligned with test scenarios ──────────────────────────────────────────
    # GENUINE_PASSPORT: real MATCH
    ("N1234567", "JOHN MICHAEL SMITH", "12/04/1990", "INDIAN", "M",
     "passport", "11/04/2030", "ACTIVE"),
    # MULTIPLE_IDENTITIES: deliberate MISMATCH (different name)
    ("N7654321", "PRIYA RAMESH NAIR", "23/08/1988", "INDIAN", "F",
     "passport", "22/08/2028", "ACTIVE"),

    # ── Synthetic Indian passports ───────────────────────────────────────────
    ("M9988776", "AMIT KUMAR SHARMA", "05/11/1985", "INDIAN", "M",
     "passport", "04/11/2029", "ACTIVE"),
    ("M5544332", "SUNITA DEVI YADAV", "17/02/1992", "INDIAN", "F",
     "passport", "16/02/2027", "ACTIVE"),
    ("K1122334", "RAJESH SINGH RATHORE", "30/06/1979", "INDIAN", "M",
     "passport", "29/06/2024", "EXPIRED"),
    ("K7788990", "ANJALI PATEL MEHTA", "09/09/1995", "INDIAN", "F",
     "passport", "08/09/2031", "ACTIVE"),
    ("L2233445", "VIKRAM SINGH CHAUHAN", "14/01/1983", "INDIAN", "M",
     "passport", "13/01/2028", "ACTIVE"),
    ("L6677889", "DEEPIKA RANI VERMA", "21/12/1991", "INDIAN", "F",
     "passport", "20/12/2026", "ACTIVE"),
    ("J3344556", "SURESH CHANDRA GUPTA", "03/03/1975", "INDIAN", "M",
     "passport", "02/03/2025", "REVOKED"),
    ("J8899001", "KAVITA SHARMA JOSHI", "27/07/1989", "INDIAN", "F",
     "passport", "26/07/2029", "ACTIVE"),

    # ── Real dataset — Indian Passport (publicly available sample) ───────────
    # RAMADUGULA SITA MAHA LAKSHMI — sample passport from immihelp.com
    # Status EXPIRED: passport expired 10/10/2021.
    ("J8369854", "RAMADUGULA SITA MAHA LAKSHMI", "23/09/1959", "INDIAN", "F",
     "passport", "10/10/2021", "EXPIRED"),
    # THAPLIVAL GARIMA — Indian passport biopage 2025 sample
    ("SP003369", "THAPLIVAL GARIMA", "01/07/1994", "INDIAN", "F",
     "passport", "03/09/2024", "EXPIRED"),

    # ── Nepali passports ─────────────────────────────────────────────────────
    ("NP112233", "BIKRAM THAPA MAGAR", "11/05/1987", "NEPALI", "M",
     "passport", "10/05/2027", "ACTIVE"),
    ("NP445566", "SITA KUMARI GURUNG", "19/10/1993", "NEPALI", "F",
     "passport", "18/10/2028", "ACTIVE"),
    ("NP778899", "RAM BAHADUR TAMANG", "02/02/1981", "NEPALI", "M",
     "passport", "01/02/2026", "ACTIVE"),
    # Passport used in Nepal visa T246414719 (from dataset)
    ("YB3773974", "DEMO TRAVELER NEPAL VISA 2024", "15/06/1990", "SPANISH", "M",
     "passport", "14/06/2030", "ACTIVE"),

    # ── Bhutanese passports ──────────────────────────────────────────────────
    ("BT100200", "TASHI WANGCHUK DORJI", "25/04/1990", "BHUTANESE", "M",
     "passport", "24/04/2030", "ACTIVE"),
    ("BT300400", "PEMA YANGZOM CHODEN", "16/08/1994", "BHUTANESE", "F",
     "passport", "15/08/2029", "ACTIVE"),
    # From Bhutan passport test scenarios
    ("G000000", "SONAM DEMA", "02/04/1991", "BHUTANESE", "F",
     "passport", "10/12/2027", "ACTIVE"),
    ("G030178", "SONAM YOUNTEN", "14/03/1987", "BHUTANESE", "M",
     "passport", "27/04/2016", "EXPIRED"),

    # ── Bhutan Citizenship Cards (from dataset) ───────────────────────────────
    ("10712002883", "PHUNTSHO TASHI", "26/12/2000", "BHUTANESE", "M",
     "national_id", "01/01/2099", "ACTIVE"),
    # Dawa Lhamo Sherpa — CID redacted in image; use synthetic number
    ("10701998042", "DAWA LHAMO SHERPA", "14/04/1998", "BHUTANESE", "F",
     "national_id", "01/01/2099", "ACTIVE"),

    # ── Bhutan DLs (from DL test scenarios) ─────────────────────────────────
    ("T-6101", "KARMA DENDUP", "01/01/1974", "BHUTANESE", "M",
     "driving_licence", "06/01/2029", "ACTIVE"),
    ("G-18638", "AMIR RAI", "25/04/2000", "BHUTANESE", "M",
     "driving_licence", "19/08/2029", "ACTIVE"),

    # ── Nepal Citizenship/NRI ─────────────────────────────────────────────────
    # Nepal Citizenship 16378-256 (Pushpa Kamal Dahal — public record)
    ("16378-256", "PUSHPA KAMAL DAHAL", "25/08/1954", "NEPALI", "M",
     "national_id", "01/01/2099", "ACTIVE"),
    # Nepal NRI Card KATH-B/1 (Dev Man Hirachan) — EXPIRED 2012
    ("KATH-B/1", "DEV MAN HIRACHAN", "01/01/1955", "NEPALI", "M",
     "national_id", "10/02/2012", "EXPIRED"),

    # ── Nepal Tourist Visas (from dataset) ───────────────────────────────────
    ("T220281095", "DEMO NEPAL VISA 2022", "01/01/1990", "UNSPECIFIED", "U",
     "visa", "24/10/2022", "EXPIRED"),
    ("T246414719", "DEMO NEPAL VISA OCT 2024", "01/01/1990", "UNSPECIFIED", "U",
     "visa", "09/11/2024", "EXPIRED"),
    ("T24013", "DEMO NEPAL VISA MAR 2024", "01/01/1990", "UNSPECIFIED", "U",
     "visa", "30/03/2024", "EXPIRED"),

    # ── Indian Visas (from dataset) ──────────────────────────────────────────
    # AF713645 — in blacklist as FORGERY, but also in citizen registry as
    # the original valid record (to demonstrate MISMATCH — blacklist overrides)
    ("AF713645", "DEMO INDIA VISA HOLDER", "01/01/1980", "GERMAN", "M",
     "visa", "22/02/2009", "EXPIRED"),

    # ── Indian national IDs / DLs ─────────────────────────────────────────────
    ("H5566778", "ARUN PRAKASH TIWARI", "08/01/1986", "INDIAN", "M",
     "national_id", "01/01/2099", "ACTIVE"),
    ("H9900112", "MEERA LAKSHMI IYER", "12/06/1997", "INDIAN", "F",
     "national_id", "01/01/2099", "ACTIVE"),
    ("G3344990", "SANJAY DUTT BHATIA", "29/09/1978", "INDIAN", "M",
     "driving_licence", "28/09/2033", "ACTIVE"),
    ("G6677001", "POOJA AGARWAL SAXENA", "04/04/1996", "INDIAN", "F",
     "driving_licence", "03/04/2036", "ACTIVE"),
    # Indian DLs from dataset — registered as valid at issuance
    ("TS00420140004496", "UPENDRAM D MUTHAIAH", "01/01/1970", "INDIAN", "M",
     "driving_licence", "03/10/2029", "ACTIVE"),
    ("GJ0519940112841", "CHETAN CHAUHAN", "02/01/1974", "INDIAN", "M",
     "driving_licence", "01/01/2024", "EXPIRED"),
    ("MH1320070019358", "SURYAKANT BIRAJDAR", "01/06/1977", "INDIAN", "M",
     "driving_licence", "06/12/2016", "EXPIRED"),

    # ── Permits ───────────────────────────────────────────────────────────────
    ("F1122998", "MOHAN LAL PRAJAPATI", "22/11/1982", "INDIAN", "M",
     "permit", "21/11/2025", "ACTIVE"),
    ("ILP-AR-2024-0088", "RAHUL SINGH THAKUR", "17/03/1995", "INDIAN", "M",
     "permit", "17/03/2025", "ACTIVE"),
    ("ILP-MN-2024-0412", "PRIYA DEVI SHARMA", "05/08/1993", "INDIAN", "F",
     "permit", "05/08/2025", "ACTIVE"),
    ("ILP-AR-2024-0091", "DEMO FORGED ILP HOLDER", "01/01/2000", "INDIAN", "M",
     "permit", "31/12/2024", "REVOKED"),
]


def seed_citizen_registry() -> None:
    db = SessionLocal()
    try:
        added = 0
        for row in DEMO_ENTRIES:
            document_number, full_name, dob, nationality, gender, doc_type, expiry, status = row
            if find_by_document_number(db, document_number) is not None:
                print(f"  skip  '{document_number}' — already exists.")
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
            print(f"  added '{document_number}' ({full_name})")
            added += 1
        print(f"Citizen registry seeder: {added} new entries added.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_citizen_registry()
