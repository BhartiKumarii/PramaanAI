"""Testing mode endpoints for generating synthetic test scenarios.
Only available in non-production environments. /submit-screening runs a
scenario through the real screening pipeline (app.api.routes.documents.
screen_document) — the same code path a real device hits — so results
here are genuinely computed, not canned strings (see that function's
docstring, and _generate_scenario_data's below)."""
import uuid
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import (
    get_blockchain_service,
    get_deepfake_provider,
    get_face_detector,
    get_liveness_provider,
    get_risk_engine,
    get_tampering_provider,
    get_validation_engine,
)
from app.api.routes.documents import screen_document
from app.core.config import get_settings
from app.core.security import require_role
from app.db.session import get_db
from app.models.user import User
from app.schemas.verification import ScreeningSubmission
from app.services.blockchain.base import BlockchainService
from app.services.deepfake.base import DeepfakeProvider
from app.services.face.base import FaceDetector
from app.services.face.embedding import extract_embedding
from app.services.liveness.base import LivenessProvider
from app.services.tampering.base import TamperingProvider
from app.services.risk.base import RiskEngine
from app.services.validation.base import ValidationEngine
from tests.synthetic_documents import (
    generate_passport_image,
    generate_visa_image,
    generate_passport_back_image,
    generate_mrz_lines,
    generate_face_like_image,
    stack_images_vertically,
    load_real_document_image,
    crop_passport_photo_region,
    crop_driving_license_photo_region,
)

router = APIRouter(prefix="/testing", tags=["testing"])


class TestScenario(str, Enum):
    GENUINE_PASSPORT = "genuine_passport"
    FAKE_PASSPORT = "fake_passport"
    FAKE_VISA = "fake_visa"
    AI_GENERATED_DOCUMENT = "ai_generated_document"
    ALTERED_PHOTO = "altered_photo"
    MODIFIED_DOB = "modified_dob"
    TAMPERED_VISA_STAMP = "tampered_visa_stamp"
    EXPIRED_PASSPORT = "expired_passport"
    EXPIRED_VISA = "expired_visa"
    BLACKLISTED_DEMO_DOCUMENT = "blacklisted_demo_document"
    INVALID_MRZ = "invalid_mrz"
    MISSING_MRZ = "missing_mrz"
    POSSIBLE_IMPERSONATION = "possible_impersonation"
    MULTIPLE_IDENTITIES = "multiple_identities"
    DUPLICATE_DOCUMENT = "duplicate_document"
    DRIVING_LICENCE_MISMATCH = "driving_licence_mismatch"
    POOR_LIGHTING = "poor_lighting"
    BLUR = "blur"
    GLARE = "glare"
    TILTED_DOCUMENT = "tilted_document"
    DOCUMENT_OUTSIDE_FRAME = "document_outside_frame"
    NO_DOCUMENT = "no_document"
    MULTIPLE_DOCUMENTS = "multiple_documents"
    FLAGGED_DEVICE = "flagged_device"
    REVOKED_DEVICE = "revoked_device"
    UNUSUAL_OFFICER_ACTIVITY = "unusual_officer_activity"
    SYSTEM_HEALTH_FAILURE = "system_health_failure"
    BHUTAN_PASSPORT_VALID = "bhutan_passport_valid"
    BHUTAN_PASSPORT_EXPIRED = "bhutan_passport_expired"
    BHUTAN_DL_KARMA_VALID = "bhutan_dl_karma_valid"
    BHUTAN_DL_AMIR_VALID = "bhutan_dl_amir_valid"
    BHUTAN_DL_CROSS_FACE = "bhutan_dl_cross_face"
    # All 5 document types — real dataset
    BHUTAN_CID_PHUNTSHO = "bhutan_cid_phuntsho"
    NEPAL_TOURIST_VISA = "nepal_tourist_visa"
    INDIA_EVISA = "india_evisa"
    INDIA_DL_EXPIRED_BLACKLISTED = "india_dl_expired_blacklisted"
    INDIA_PASSPORT_SAMPLE = "india_passport_sample"
    INDIA_VISA_EXPIRED_BLACKLISTED = "india_visa_expired_blacklisted"
    NEPAL_CITIZENSHIP_NOTABLE = "nepal_citizenship_notable"
    ILP_FORGED = "ilp_forged"


class TestScenarioRequest(BaseModel):
    scenario: TestScenario
    device_id: uuid.UUID | None = None
    officer_id: uuid.UUID | None = None


class TestScenarioResponse(BaseModel):
    scenario: TestScenario
    description: str
    expected_risk_level: str
    expected_issues: list[str]
    document_image: str | None = None  # base64
    selfie_image: str | None = None  # base64
    ocr_fields: dict[str, str] = Field(default_factory=dict)
    mrz_text: str | None = None


SCENARIO_DESCRIPTIONS = {
    TestScenario.GENUINE_PASSPORT: (
        "A valid, unexpired passport with correct MRZ, matching photo, "
        "and consistent data fields. Should result in LOW RISK."
    ),
    TestScenario.FAKE_PASSPORT: (
        "A passport with inconsistent fonts, spacing anomalies, and "
        "invalid MRZ check digits. Signals possible counterfeit document."
    ),
    TestScenario.FAKE_VISA: (
        "A visa with mismatched visa number format, invalid issue/expiry "
        "dates, and visual artifacts suggesting digital manipulation."
    ),
    TestScenario.AI_GENERATED_DOCUMENT: (
        "Document image with AI-generation artifacts: unnatural texture "
        "uniformity, impossible lighting consistency, compression anomalies."
    ),
    TestScenario.ALTERED_PHOTO: (
        "Passport with a substituted photograph. Face embedding mismatch "
        "between document photo and live capture expected."
    ),
    TestScenario.MODIFIED_DOB: (
        "Date of birth in MRZ differs from visual inspection zone. "
        "Cross-field validation should flag this inconsistency."
    ),
    TestScenario.TAMPERED_VISA_STAMP: (
        "Visa stamp shows ELA anomalies indicating digital splicing or "
        "physical alteration. Tampering detection should flag."
    ),
    TestScenario.EXPIRED_PASSPORT: (
        "Passport with expiry date in the past. Document expiry check "
        "should contribute to risk score."
    ),
    TestScenario.EXPIRED_VISA: (
        "Visa with validity period ended. Should flag as expired."
    ),
    TestScenario.BLACKLISTED_DEMO_DOCUMENT: (
        "Document number matches a known demo blacklist entry. "
        "Should hard-override to HIGH RISK."
    ),
    TestScenario.INVALID_MRZ: (
        "MRZ present but check digits fail validation. MRZ validation "
        "should fail and contribute to risk."
    ),
    TestScenario.MISSING_MRZ: (
        "No machine-readable zone detected. Missing MRZ signal."
    ),
    TestScenario.POSSIBLE_IMPERSONATION: (
        "Live selfie face embedding significantly differs from document "
        "photo embedding. Possible impersonation signal."
    ),
    TestScenario.MULTIPLE_IDENTITIES: (
        "Same face embedding linked to multiple distinct identities "
        "in the identity graph. Cluster alert expected."
    ),
    TestScenario.DUPLICATE_DOCUMENT: (
        "Same document number submitted from different devices/officers. "
        "Reused document detection should flag."
    ),
    TestScenario.DRIVING_LICENCE_MISMATCH: (
        "Driving licence fields (name, DOB) don't match passport. "
        "Cross-document validation failure."
    ),
    TestScenario.POOR_LIGHTING: (
        "Document captured in low light. Quality metrics should show "
        "low lighting score."
    ),
    TestScenario.BLUR: (
        "Blurred document capture. Blur quality metric should be low."
    ),
    TestScenario.GLARE: (
        "Strong glare/reflection on document. Glare quality metric high."
    ),
    TestScenario.TILTED_DOCUMENT: (
        "Document at significant angle. Alignment score should be low."
    ),
    TestScenario.DOCUMENT_OUTSIDE_FRAME: (
        "Document not fully within capture frame. Edge detection fails."
    ),
    TestScenario.NO_DOCUMENT: (
        "No document detected in frame. Empty capture."
    ),
    TestScenario.MULTIPLE_DOCUMENTS: (
        "Multiple document-like objects in frame. Should flag ambiguity."
    ),
    TestScenario.FLAGGED_DEVICE: (
        "Screening submitted from a device previously flagged for "
        "unusual volume or sync failures."
    ),
    TestScenario.REVOKED_DEVICE: (
        "Screening from a revoked device. Should be rejected."
    ),
    TestScenario.UNUSUAL_OFFICER_ACTIVITY: (
        "Officer with anomalous screening patterns (volume, timing, "
        "location changes)."
    ),
    TestScenario.SYSTEM_HEALTH_FAILURE: (
        "Simulated degradation in OCR, face matching, or risk engine "
        "services."
    ),
    TestScenario.BHUTAN_PASSPORT_VALID: (
        "Kingdom of Bhutan TD3 passport — bearer SONAM DEMA, DOB 02/04/1991, "
        "passport no. G000000 (all-zeros; suspicious but as printed). "
        "Valid until 10/12/2027. No back-page image supplied; MRZ generated "
        "from the front-page data. Selfie is a face cropped from the document "
        "photo itself. Expected LOW–MEDIUM risk: valid document, possible flag "
        "on unusual all-zero passport number."
    ),
    TestScenario.BHUTAN_PASSPORT_EXPIRED: (
        "Kingdom of Bhutan TD3 passport — bearer SONAM YOUNTEN, DOB 14/03/1987, "
        "passport no. G030178. EXPIRED 27/04/2016 (over 9 years ago). "
        "Document is stamped SAMPLE. No back-page image supplied; MRZ generated "
        "from the front-page data. Selfie is a face cropped from the document "
        "photo. Expected MEDIUM–HIGH risk: document clearly expired."
    ),
    TestScenario.BHUTAN_DL_KARMA_VALID: (
        "Kingdom of Bhutan Driving License — bearer KARMA DENDUP, CID 10702001841, "
        "DOB 01/01/1974, License No. T-6101, valid until 06/01/2029. "
        "Selfie is Karma Dendup's own face cropped from the license. "
        "No MRZ on driving licenses. Expected LOW–MEDIUM risk: valid document, "
        "same-person face comparison."
    ),
    TestScenario.BHUTAN_DL_AMIR_VALID: (
        "Kingdom of Bhutan Driving License — bearer AMIR RAI, CID 11301001552, "
        "DOB 25/04/2000, License No. G-18638, valid until 19/08/2029. "
        "Selfie is Amir Rai's own face cropped from the license. "
        "No MRZ on driving licenses. Expected LOW–MEDIUM risk: valid document, "
        "same-person face comparison."
    ),
    TestScenario.BHUTAN_DL_CROSS_FACE: (
        "Kingdom of Bhutan Driving License — bearer KARMA DENDUP (T-6101), but the "
        "selfie is AMIR RAI's face. Cross-document face substitution. "
        "Expected HIGH risk: face mismatch — possible impersonation."
    ),
    TestScenario.BHUTAN_CID_PHUNTSHO: (
        "Kingdom of Bhutan Citizenship Card — PHUNTSHO TASHI, CID 10712002883, "
        "DOB 26/12/2000, Male. National ID document type. No MRZ. "
        "Selfie cropped from card photo. Expected LOW–MEDIUM risk: valid ID."
    ),
    TestScenario.NEPAL_TOURIST_VISA: (
        "Government of Nepal Tourist Visa sticker — Visa No T220281095, "
        "issued 10/10/2022, validity 15 days, expired 24/10/2022. "
        "Issued at Tribhuvan International Airport. "
        "Expected MEDIUM risk: visa expired."
    ),
    TestScenario.INDIA_EVISA: (
        "Indian e-Visa (Electronic Travel Authorization) — eTourist Visa, "
        "Nationality SPAIN, Double entry, issued 30/09/2019, expired 29/10/2019. "
        "Expected MEDIUM risk: e-Visa expired."
    ),
    TestScenario.INDIA_DL_EXPIRED_BLACKLISTED: (
        "India Gujarat State Driving Licence — CHETAN CHAUHAN, "
        "DL No GJ05-19940112841, DOB 02/01/1974, expired 01/01/2024. "
        "Document number is in the watchlist (reported stolen after expiry). "
        "Expected HIGH risk: expired + blacklisted."
    ),
    TestScenario.INDIA_PASSPORT_SAMPLE: (
        "India passport sample — RAMADUGULA SITA MAHA LAKSHMI, "
        "Passport J8369854, DOB 23/09/1959, Female, Indian. "
        "Expired 10/10/2021. SAMPLE document from public source. "
        "MRZ: P<INDRAMADUGULA<<SITA<MAHA<LAKSHMI. "
        "Expected MEDIUM risk: expired passport."
    ),
    TestScenario.INDIA_VISA_EXPIRED_BLACKLISTED: (
        "India Tourist Visa — Visa No AF713645, TV type, issued 22/08/2008, "
        "expired 22/02/2009, Munich consulate. Document number is in watchlist "
        "(reported fraudulent use 4 months after expiry). "
        "Expected HIGH risk: expired + blacklisted."
    ),
    TestScenario.NEPAL_CITIZENSHIP_NOTABLE: (
        "Nepal Citizenship Card — PUSHPA KAMAL DAHAL, No 16378-256, "
        "DOB 25/08/1954, Male, Chitwan. Notable person — former PM of Nepal. "
        "Expected MEDIUM risk: valid document, notable individual flagged for "
        "enhanced manual review."
    ),
    TestScenario.ILP_FORGED: (
        "Arunachal Pradesh Inner Line Permit — ILP-AR-2024-0091. "
        "Document number is in watchlist (forged permit — seal does not match "
        "issuing authority records). "
        "Expected HIGH risk: forged permit, blacklisted."
    ),
}


def _base64_encode(data: bytes) -> str:
    import base64
    return base64.b64encode(data).decode("ascii")


@router.get(
    "/scenarios",
    summary="List all available test scenarios (non-production only)",
)
def list_scenarios(
    _user: User = Depends(require_role()),
) -> dict[str, Any]:
    if get_settings().ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Testing endpoints disabled in production",
        )
    return {
        "scenarios": [
            {
                "id": s.value,
                "name": s.value.replace("_", " ").title(),
                "description": SCENARIO_DESCRIPTIONS[s],
            }
            for s in TestScenario
        ]
    }


def _generate_scenario_data(scenario: TestScenario) -> dict:
    """The actual synthetic-data generator, shared by both /generate
    (preview) and /submit-screening (real pipeline run) — kept scenario-
    and-route-agnostic so a "real vs expected" comparison always runs
    against the exact same generated bytes.

    `front_image` keeps the original face-bearing/front-page bytes even
    after `document_image` gets a back-page MRZ image stacked onto it for
    display, so face-embedding extraction always runs against a single
    genuine image, never a multi-page composite."""
    document_image = None
    front_image = None
    selfie_image = None
    ocr_fields = {}
    mrz_text = None
    expected_risk = "LOW"
    expected_issues = []

    if scenario == TestScenario.GENUINE_PASSPORT:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)  # prepend MRZ
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "LOW"
        expected_issues = []

    elif scenario == TestScenario.FAKE_PASSPORT:
        document_image = generate_passport_image(passport_number="N123456X")  # invalid check digit
        line1, line2 = generate_mrz_lines(passport_number="N123456X")
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N123456X",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Invalid MRZ check digit", "Font inconsistency detected"]

    elif scenario == TestScenario.FAKE_VISA:
        document_image = generate_visa_image(visa_number="V998877X")
        selfie_image = generate_face_like_image(2)
        ocr_fields = {
            "visa_number": "V998877X",
            "visa_type": "TOURIST",
            "entry_validity": "SINGLE",
            "stay_duration": "30 DAYS",
        }
        expected_risk = "HIGH"
        expected_issues = ["Invalid visa number format", "Visual manipulation artifacts"]

    elif scenario == TestScenario.AI_GENERATED_DOCUMENT:
        document_image = generate_passport_image()
        selfie_image = generate_face_like_image(3)
        ocr_fields = {
            "name": "AI GENERATED NAME",
            "passport_number": "A1111111",
            "nationality": "SYNTHETIC",
            "date_of_birth": "01/01/2000",
            "date_of_expiry": "01/01/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["AI generation artifacts detected", "Unnatural texture uniformity"]

    elif scenario == TestScenario.ALTERED_PHOTO:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        # Different face for selfie = impersonation
        selfie_image = generate_face_like_image(99)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Face embedding mismatch - possible photo substitution"]

    elif scenario == TestScenario.MODIFIED_DOB:
        document_image = generate_passport_image(date_of_birth="12/04/1990", date_of_expiry="11/04/2030")
        # MRZ says different DOB
        line1, line2 = generate_mrz_lines(date_of_birth_yymmdd="850412")  # 1985 not 1990
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",  # Visual zone
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["DOB mismatch between visual zone and MRZ"]

    elif scenario == TestScenario.TAMPERED_VISA_STAMP:
        document_image = generate_visa_image()
        selfie_image = generate_face_like_image(4)
        ocr_fields = {
            "visa_number": "V9988776",
            "visa_type": "TOURIST",
            "entry_validity": "SINGLE",
            "stay_duration": "30 DAYS",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Visa stamp tampering detected via ELA"]

    elif scenario == TestScenario.EXPIRED_PASSPORT:
        document_image = generate_passport_image(date_of_expiry="11/04/2020")  # expired
        line1, line2 = generate_mrz_lines(date_of_expiry_yymmdd="200411")
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2020",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Document expired"]

    elif scenario == TestScenario.EXPIRED_VISA:
        document_image = generate_visa_image(stay_duration="EXPIRED")
        selfie_image = generate_face_like_image(5)
        ocr_fields = {
            "visa_number": "V9988776",
            "visa_type": "TOURIST",
            "entry_validity": "EXPIRED",
            "stay_duration": "0 DAYS",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Visa expired"]

    elif scenario == TestScenario.BLACKLISTED_DEMO_DOCUMENT:
        # Use a known blacklisted document number
        document_image = generate_passport_image(passport_number="BLACKLIST001")
        line1, line2 = generate_mrz_lines(passport_number="BLACKLIST001")
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "BLACKLISTED PERSON",
            "passport_number": "BLACKLIST001",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Blacklisted document number matched"]

    elif scenario == TestScenario.INVALID_MRZ:
        document_image = generate_passport_image()
        # Corrupt the MRZ check digit
        line1, line2 = generate_mrz_lines()
        corrupted_line2 = line2[:-1] + ("0" if line2[-1] != "0" else "1")
        mrz_text = f"{line1}\n{corrupted_line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, corrupted_line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["MRZ check digit validation failed"]

    elif scenario == TestScenario.MISSING_MRZ:
        document_image = generate_passport_image()
        # No MRZ lines added
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["No MRZ detected"]

    elif scenario == TestScenario.POSSIBLE_IMPERSONATION:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        # Different person's face
        selfie_image = generate_face_like_image(42)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Face embedding mismatch - possible impersonation"]

    elif scenario == TestScenario.MULTIPLE_IDENTITIES:
        document_image = generate_passport_image(name="JANE DOE", passport_number="N7654321")
        line1, line2 = generate_mrz_lines(surname="DOE", given_names="JANE", passport_number="N7654321")
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        # Same face as another identity
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JANE DOE",
            "passport_number": "N7654321",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Same face linked to multiple identities"]

    elif scenario == TestScenario.DUPLICATE_DOCUMENT:
        document_image = generate_passport_image(passport_number="N1234567")
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Document number previously submitted"]

    elif scenario == TestScenario.DRIVING_LICENCE_MISMATCH:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Driving licence data conflicts with passport"]

    elif scenario in (TestScenario.POOR_LIGHTING, TestScenario.BLUR, TestScenario.GLARE,
                       TestScenario.TILTED_DOCUMENT, TestScenario.DOCUMENT_OUTSIDE_FRAME,
                       TestScenario.NO_DOCUMENT, TestScenario.MULTIPLE_DOCUMENTS):
        # Quality issue scenarios - use base image but note quality issues
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        quality_issue_map = {
            TestScenario.POOR_LIGHTING: ("MEDIUM", ["Poor lighting detected"]),
            TestScenario.BLUR: ("MEDIUM", ["Blur detected"]),
            TestScenario.GLARE: ("MEDIUM", ["Glare/reflection detected"]),
            TestScenario.TILTED_DOCUMENT: ("MEDIUM", ["Document tilted - alignment low"]),
            TestScenario.DOCUMENT_OUTSIDE_FRAME: ("MEDIUM", ["Document outside capture frame"]),
            TestScenario.NO_DOCUMENT: ("HIGH", ["No document detected in frame"]),
            TestScenario.MULTIPLE_DOCUMENTS: ("MEDIUM", ["Multiple documents detected"]),
        }
        expected_risk, expected_issues = quality_issue_map[scenario]

    elif scenario == TestScenario.FLAGGED_DEVICE:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Device flagged for unusual activity"]

    elif scenario == TestScenario.REVOKED_DEVICE:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "HIGH"
        expected_issues = ["Device revoked - screening rejected"]

    elif scenario == TestScenario.UNUSUAL_OFFICER_ACTIVITY:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Unusual officer screening pattern detected"]

    elif scenario == TestScenario.SYSTEM_HEALTH_FAILURE:
        document_image = generate_passport_image()
        line1, line2 = generate_mrz_lines()
        mrz_text = f"{line1}\n{line2}"
        front_image = document_image
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = generate_face_like_image(1)
        ocr_fields = {
            "name": "JOHN MICHAEL SMITH",
            "passport_number": "N1234567",
            "nationality": "INDIAN",
            "date_of_birth": "12/04/1990",
            "date_of_expiry": "11/04/2030",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["System health degraded - limited validation"]

    elif scenario == TestScenario.BHUTAN_PASSPORT_VALID:
        import os
        img_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "tests", "data", "bhutan_passport_sonam_dema.jpg",
        )
        front_image = load_real_document_image(os.path.normpath(img_path))
        # No back-page photo supplied; generate a clean MRZ from the known fields.
        line1, line2 = generate_mrz_lines(
            surname="DEMA",
            given_names="SONAM",
            passport_number="G000000",
            issuing_country="BTN",
            nationality="BTN",
            date_of_birth_yymmdd="910402",
            sex="F",
            date_of_expiry_yymmdd="271210",
            personal_number="107010007360",
        )
        mrz_text = f"{line1}\n{line2}"
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        # Selfie: crop the bearer's photo from the passport image itself —
        # we expect a match (face in the document == person presenting it).
        selfie_image = crop_passport_photo_region(front_image)
        ocr_fields = {
            "name": "SONAM DEMA",
            "passport_number": "G000000",
            "nationality": "BHUTANESE",
            "date_of_birth": "02/04/1991",
            "date_of_expiry": "10/12/2027",
            "gender": "F",
            "place_of_birth": "THIMPHU",
            "issuing_authority": "FOREIGN MINISTRY, THIMPHU",
        }
        expected_risk = "MEDIUM"
        expected_issues = [
            "Unusual passport number (all zeros — G000000): verify document authenticity",
        ]

    elif scenario == TestScenario.BHUTAN_PASSPORT_EXPIRED:
        import os
        img_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "..",
            "tests", "data", "bhutan_passport_sonam_younten.jpg",
        )
        front_image = load_real_document_image(os.path.normpath(img_path))
        # No back-page photo supplied; generate MRZ from the known fields.
        line1, line2 = generate_mrz_lines(
            surname="YOUNTEN",
            given_names="SONAM",
            passport_number="G030178",
            issuing_country="BTN",
            nationality="BTN",
            date_of_birth_yymmdd="870314",
            sex="M",
            date_of_expiry_yymmdd="160427",
            personal_number="105030001180",
        )
        mrz_text = f"{line1}\n{line2}"
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = crop_passport_photo_region(front_image)
        ocr_fields = {
            "name": "SONAM YOUNTEN",
            "passport_number": "G030178",
            "nationality": "BHUTANESE",
            "date_of_birth": "14/03/1987",
            "date_of_expiry": "27/04/2016",
            "gender": "M",
            "place_of_birth": "THIMPHU",
            "issuing_authority": "FOREIGN MINISTRY, THIMPHU",
        }
        expected_risk = "HIGH"
        expected_issues = [
            "Document expired 27/04/2016 — expired over 9 years ago",
            "Document stamped SAMPLE — verify this is not a specimen copy",
        ]

    elif scenario in (TestScenario.BHUTAN_DL_KARMA_VALID, TestScenario.BHUTAN_DL_AMIR_VALID, TestScenario.BHUTAN_DL_CROSS_FACE):
        import os
        karma_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "bhutan_dl_karma_dendup.jpg"))
        amir_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "bhutan_dl_amir_rai.jpg"))

        karma_img = load_real_document_image(karma_path)
        amir_img = load_real_document_image(amir_path)

        if scenario == TestScenario.BHUTAN_DL_KARMA_VALID:
            front_image = karma_img
            document_image = karma_img
            # Selfie = Karma's own face from the license
            selfie_image = crop_driving_license_photo_region(karma_img)
            ocr_fields = {
                "name": "KARMA DENDUP",
                "license_number": "T-6101",
                "nationality": "BHUTANESE",
                "date_of_birth": "01/01/1974",
                "date_of_expiry": "06/01/2029",
                "cid_number": "10702001841",
                "blood_group": "O Positive",
                "issued_date": "08/02/2019",
                "address": "Chali, Monggar",
            }
            expected_risk = "LOW"
            expected_issues = []

        elif scenario == TestScenario.BHUTAN_DL_AMIR_VALID:
            front_image = amir_img
            document_image = amir_img
            selfie_image = crop_driving_license_photo_region(amir_img)
            ocr_fields = {
                "name": "AMIR RAI",
                "license_number": "G-18638",
                "nationality": "BHUTANESE",
                "date_of_birth": "25/04/2000",
                "date_of_expiry": "19/08/2029",
                "cid_number": "11301001552",
                "blood_group": "B Positive",
                "issued_date": "19/08/2019",
                "address": "Samtenling, Sarpang",
            }
            expected_risk = "LOW"
            expected_issues = []

        else:  # BHUTAN_DL_CROSS_FACE
            # Document = Karma Dendup's license, Selfie = Amir Rai's face
            front_image = karma_img
            document_image = karma_img
            selfie_image = crop_driving_license_photo_region(amir_img)
            ocr_fields = {
                "name": "KARMA DENDUP",
                "license_number": "T-6101",
                "nationality": "BHUTANESE",
                "date_of_birth": "01/01/1974",
                "date_of_expiry": "06/01/2029",
                "cid_number": "10702001841",
                "blood_group": "O Positive",
                "issued_date": "08/02/2019",
                "address": "Chali, Monggar",
            }
            expected_risk = "HIGH"
            expected_issues = [
                "Face mismatch — selfie does not match document photo (cross-document substitution)",
                "Possible impersonation: document belongs to KARMA DENDUP, selfie is a different person",
            ]

    elif scenario == TestScenario.BHUTAN_CID_PHUNTSHO:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "bhutan", "citizenship_phuntsho_tashi.jpg"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = crop_driving_license_photo_region(front_image)
        ocr_fields = {
            "name": "PHUNTSHO TASHI",
            "document_number": "10712002883",
            "nationality": "BHUTANESE",
            "date_of_birth": "26/12/2000",
            "gender": "M",
            "document_type_label": "Citizenship Card",
        }
        expected_risk = "LOW"
        expected_issues = []

    elif scenario == TestScenario.NEPAL_TOURIST_VISA:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "nepal", "visa_t220281095.png"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = generate_face_like_image(7)
        ocr_fields = {
            "visa_number": "T220281095",
            "visa_type": "TOURIST",
            "entry_validity": "SINGLE",
            "stay_duration": "15 DAYS",
            "date_of_expiry": "24/10/2022",
            "issued_date": "10/10/2022",
            "issued_at": "Tribhuvan International Airport (TIA)",
        }
        mrz_text = None
        expected_risk = "MEDIUM"
        expected_issues = ["Nepal tourist visa expired 24/10/2022"]

    elif scenario == TestScenario.INDIA_EVISA:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "india", "evisa_spain.jpg"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = generate_face_like_image(8)
        ocr_fields = {
            "visa_number": "ETA-DEMO-SPAIN-2019",
            "visa_type": "eTOURIST",
            "nationality": "SPANISH",
            "entry_validity": "DOUBLE",
            "stay_duration": "30 DAYS",
            "date_of_expiry": "29/10/2019",
            "issued_date": "30/09/2019",
        }
        mrz_text = None
        expected_risk = "MEDIUM"
        expected_issues = ["Indian e-Visa expired 29/10/2019"]

    elif scenario == TestScenario.INDIA_DL_EXPIRED_BLACKLISTED:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "india", "dl_gj05_chetan_expired.jpg"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = crop_driving_license_photo_region(front_image)
        ocr_fields = {
            "name": "CHETAN CHAUHAN",
            "license_number": "GJ0519940112841",
            "nationality": "INDIAN",
            "date_of_birth": "02/01/1974",
            "date_of_expiry": "01/01/2024",
            "issued_date": "16/08/1994",
            "blood_group": "O+",
            "address": "28, Parixit Society, Surat 395007",
        }
        mrz_text = None
        expected_risk = "HIGH"
        expected_issues = [
            "Driving licence expired 01/01/2024",
            "Document number GJ0519940112841 found in watchlist — reported stolen after expiry",
        ]

    elif scenario == TestScenario.INDIA_PASSPORT_SAMPLE:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "india", "passport_ramadugula_sample.jpg"))
        front_image = load_real_document_image(img_path)
        # Generate MRZ from the known passport data
        line1, line2 = generate_mrz_lines(
            surname="RAMADUGULA",
            given_names="SITA MAHA LAKSHMI",
            passport_number="J8369854",
            issuing_country="IND",
            nationality="IND",
            date_of_birth_yymmdd="590923",
            sex="F",
            date_of_expiry_yymmdd="211010",
        )
        mrz_text = f"{line1}\n{line2}"
        document_image = stack_images_vertically(generate_passport_back_image(line1, line2), front_image)
        selfie_image = crop_passport_photo_region(front_image)
        ocr_fields = {
            "name": "RAMADUGULA SITA MAHA LAKSHMI",
            "passport_number": "J8369854",
            "nationality": "INDIAN",
            "date_of_birth": "23/09/1959",
            "date_of_expiry": "10/10/2021",
            "gender": "F",
            "place_of_birth": "GUNDUGOLANU",
        }
        expected_risk = "MEDIUM"
        expected_issues = ["Passport expired 10/10/2021"]

    elif scenario == TestScenario.INDIA_VISA_EXPIRED_BLACKLISTED:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "india", "visa_af713645_expired.jpg"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = generate_face_like_image(9)
        ocr_fields = {
            "visa_number": "AF713645",
            "visa_type": "TV",
            "entry_validity": "MULTIPLE",
            "date_of_expiry": "22/02/2009",
            "issued_date": "22/08/2008",
            "issued_at": "Munich",
        }
        mrz_text = None
        expected_risk = "HIGH"
        expected_issues = [
            "India visa expired 22/02/2009",
            "Visa number AF713645 flagged in watchlist — reported fraudulent use after expiry",
        ]

    elif scenario == TestScenario.NEPAL_CITIZENSHIP_NOTABLE:
        import os
        img_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "tests", "data", "nepal", "citizenship_pushpa_dahal.jpg"))
        front_image = load_real_document_image(img_path)
        document_image = front_image
        selfie_image = crop_driving_license_photo_region(front_image)
        ocr_fields = {
            "name": "PUSHPA KAMAL DAHAL",
            "document_number": "16378-256",
            "nationality": "NEPALI",
            "date_of_birth": "25/08/1954",
            "gender": "M",
            "address": "Chitwan, Nepal",
        }
        mrz_text = None
        expected_risk = "MEDIUM"
        expected_issues = [
            "Document holder is a notable public figure — enhanced manual review recommended",
        ]

    elif scenario == TestScenario.ILP_FORGED:
        document_image = generate_passport_image(
            name="RAHUL FORGED PERMIT",
            passport_number="ILP-AR-2024-0091",
            nationality="INDIAN",
            date_of_birth="17/03/1995",
            date_of_expiry="17/03/2025",
        )
        front_image = document_image
        selfie_image = generate_face_like_image(10)
        ocr_fields = {
            "name": "RAHUL SINGH THAKUR",
            "permit_number": "ILP-AR-2024-0091",
            "nationality": "INDIAN",
            "date_of_birth": "17/03/1995",
            "date_of_expiry": "17/03/2025",
            "issued_by": "Deputy Commissioner, Arunachal Pradesh",
            "permit_type": "Inner Line Permit",
        }
        mrz_text = None
        expected_risk = "HIGH"
        expected_issues = [
            "Permit number ILP-AR-2024-0091 found in watchlist — forged permit, seal mismatch",
        ]

    if front_image is None:
        front_image = document_image

    return {
        "scenario": scenario,
        "description": SCENARIO_DESCRIPTIONS[scenario],
        "expected_risk_level": expected_risk,
        "expected_issues": expected_issues,
        "document_image": document_image,
        "front_image": front_image,
        "selfie_image": selfie_image,
        "ocr_fields": ocr_fields,
        "mrz_text": mrz_text,
    }


@router.post(
    "/generate",
    response_model=TestScenarioResponse,
    summary="Generate a test scenario with synthetic document images",
)
def generate_scenario(
    request: TestScenarioRequest,
    _user: User = Depends(require_role()),
) -> TestScenarioResponse:
    if get_settings().ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Testing endpoints disabled in production",
        )
    data = _generate_scenario_data(request.scenario)
    return TestScenarioResponse(
        scenario=data["scenario"],
        description=data["description"],
        expected_risk_level=data["expected_risk_level"],
        expected_issues=data["expected_issues"],
        document_image=_base64_encode(data["document_image"]) if data["document_image"] else None,
        selfie_image=_base64_encode(data["selfie_image"]) if data["selfie_image"] else None,
        ocr_fields=data["ocr_fields"],
        mrz_text=data["mrz_text"],
    )


@router.post(
    "/submit-screening",
    summary="Run a generated test scenario through the real screening pipeline",
)
def submit_test_screening(
    request: TestScenarioRequest,
    user: User = Depends(require_role()),
    validation_engine: ValidationEngine = Depends(get_validation_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    blockchain_service: BlockchainService = Depends(get_blockchain_service),
    face_detector: FaceDetector = Depends(get_face_detector),
    tampering_provider: TamperingProvider = Depends(get_tampering_provider),
    deepfake_provider: DeepfakeProvider = Depends(get_deepfake_provider),
    liveness_provider: LivenessProvider = Depends(get_liveness_provider),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Unlike the old version of this endpoint, this genuinely runs the
    scenario through the real risk engine and returns a real
    ScreeningResponse — `expected_risk_level`/`expected_issues` describe
    what the scenario was *designed* to exercise (a hypothesis, written
    by hand when the scenario was authored); `actual_result` is what the
    real pipeline actually computed just now. They are shown side by
    side deliberately, since the whole point of a test scenario is to
    check whether the two agree — never presented as if one confirms the
    other automatically."""
    if get_settings().ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Testing endpoints disabled in production",
        )

    data = _generate_scenario_data(request.scenario)
    if not data["ocr_fields"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"scenario {request.scenario.value!r} has no ocr_fields — cannot run through the screening pipeline",
        )

    document_type = "visa" if "visa" in request.scenario.value else "passport"
    document_face_embedding = extract_embedding(data["front_image"]) if data["front_image"] else None
    live_face_embedding = extract_embedding(data["selfie_image"]) if data["selfie_image"] else None
    # Real YuNet detection over the actual generated selfie bytes — these
    # are synthetic "face-like" test images, not real photos, so
    # NO_FACE is often the honest, correct result here, not a bug.
    face_detection_result = face_detector.detect(data["selfie_image"]) if data["selfie_image"] else None
    # Tampering/deepfake need pixel-level analysis that can normally only
    # happen on-device (see ScreeningSubmission's docstring) — but here,
    # server-side, the raw bytes genuinely exist in-process, so running
    # them for real is strictly more honest than leaving these scenarios
    # (several literally named for tampering/deepfake cases) untested.
    tampering_result = tampering_provider.analyze(data["front_image"]) if data["front_image"] else None
    deepfake_result = deepfake_provider.analyze(data["front_image"]) if data["front_image"] else None
    liveness_result = liveness_provider.analyze(data["selfie_image"]) if data["selfie_image"] else None

    submission = ScreeningSubmission(
        document_type=document_type,
        nationality=data["ocr_fields"].get("nationality", "INDIAN"),
        ocr_fields=data["ocr_fields"],
        ocr_confidence=0.85,
        mrz_text=data["mrz_text"],
        document_face_embedding=document_face_embedding,
        live_face_embedding=live_face_embedding,
        face_detection_result=face_detection_result,
        tampering_result=tampering_result,
        deepfake_result=deepfake_result,
        liveness_result=liveness_result,
    )

    real_result = screen_document(
        payload=submission,
        _user=user,
        validation_engine=validation_engine,
        risk_engine=risk_engine,
        blockchain_service=blockchain_service,
        db=db,
    )

    return {
        "scenario": request.scenario.value,
        "description": data["description"],
        "designed_to_exercise": {
            "expected_risk_level": data["expected_risk_level"],
            "expected_issues": data["expected_issues"],
        },
        "actual_result": real_result.model_dump(),
    }