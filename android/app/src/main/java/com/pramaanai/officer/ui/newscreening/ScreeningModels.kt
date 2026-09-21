package com.pramaanai.officer.ui.newscreening

import androidx.annotation.StringRes
import com.pramaanai.officer.R

enum class DocumentType(
    val value: String,
    @StringRes val labelRes: Int,
    @StringRes val subtitleRes: Int,
) {
    PASSPORT(
        "passport",
        R.string.doc_type_passport,
        R.string.doc_type_passport_sub,
    ),
    VISA(
        "visa",
        R.string.doc_type_visa,
        R.string.doc_type_visa_sub,
    ),
    NATIONAL_ID(
        "national_id",
        R.string.doc_type_national_id,
        R.string.doc_type_national_id_sub,
    ),
    DRIVING_LICENCE(
        "driving_licence",
        R.string.doc_type_driving_licence,
        R.string.doc_type_driving_licence_sub,
    ),
    PERMIT(
        "permit",
        R.string.doc_type_permit,
        R.string.doc_type_permit_sub,
    ),
}

data class ScreeningData(
    val documentType: DocumentType,
    val checkpointCode: String?,
)
