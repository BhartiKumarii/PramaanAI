package com.pramaanai.officer.ui.newscreening

enum class DocumentType(
    val value: String,
    val displayName: String,
) {
    PASSPORT("passport", "Passport"),
    NATIONAL_ID("national_id", "National ID"),
    VISA("visa", "Visa"),
    DRIVING_LICENCE("driving_licence", "Driving Licence"),
    PERMIT("permit", "Permit"),
}

// Only the document type is known before scanning — every other field
// (name, document number, DOB, expiry, nationality) comes from on-device
// OCR after capture. The officer may correct an obviously-wrong OCR
// value, but nothing is forced — a field the scan couldn't read just
// flows through as-is, never a hand-typed stand-in for real OCR (see
// CaptureScreen.kt's submit()).
data class ScreeningData(
    val documentType: DocumentType,
    val checkpointCode: String?,
)