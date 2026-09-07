import enum


class DocumentType(str, enum.Enum):
    PASSPORT = "passport"
    VISA = "visa"
    NATIONAL_ID = "national_id"
    DRIVING_LICENCE = "driving_licence"
    PERMIT = "permit"
