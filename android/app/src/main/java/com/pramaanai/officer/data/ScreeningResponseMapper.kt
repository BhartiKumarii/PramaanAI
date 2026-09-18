package com.pramaanai.officer.data

import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.data.remote.ScreeningResponse

/** Shared by [ScreeningRepository.submitScreening] (the normal online
 * path) and [com.pramaanai.officer.data.sync.PendingSubmissionWorker]
 * (the offline-queue drain path) so both build the exact same
 * [ScreeningQueueItem] shape from a real /documents/screen response —
 * no duplicated, potentially-drifting mapping logic between the two. */
fun screeningResponseToQueueItem(
    response: ScreeningResponse,
    travelerName: String,
    documentType: String,
    nationality: String,
    checkpoint: String,
    documentImagePath: String? = null,
    selfieImagePath: String? = null,
    mrzText: String? = null,
): ScreeningQueueItem = ScreeningQueueItem(
    id = response.verificationId,
    caseId = response.caseId,
    caseNumber = response.caseNumber,
    travelerName = travelerName,
    documentType = documentType,
    nationality = nationality,
    checkpoint = checkpoint,
    submittedAt = System.currentTimeMillis(),
    status = ScreeningStatus.PENDING,
    risk = response.risk,
    registryHits = response.registry?.hits ?: emptyList(),
    documentImagePath = documentImagePath,
    selfieImagePath = selfieImagePath,
    deepfakeStatus = response.deepfake?.status,
    deepfakeReason = response.deepfake?.reason,
    livenessStatus = response.liveness?.status,
    livenessReason = response.liveness?.reason,
    // The server echoes fields, not the MRZ lines; show the ones the device
    // actually read (only MRZ-shaped lines — the fallback for a document with
    // no MRZ is the whole raw OCR text, which must not be passed off as one).
    // Gson bypasses Kotlin defaults, so a missing list arrives as null.
    ocr = response.ocr?.let { o ->
        @Suppress("USELESS_CAST")
        val serverLines = (o.mrzLines as List<String>?).orEmpty()
        o.copy(
            mrzLines = serverLines.ifEmpty {
                mrzText?.lines().orEmpty().map { it.trim() }.filter { line -> line.length == 44 && line.all { it in 'A'..'Z' || it in '0'..'9' || it == '<' } }
            },
        )
    },
    validation = response.validation,
    tampering = response.tampering,
    face = response.face,
    identityGraph = response.identityGraph,
)
