package com.bordershield.officer.data.model

data class LocationBox(
    val x0: Int,
    val y0: Int,
    val x1: Int,
    val y1: Int,
)

data class RiskSignalBreakdown(
    val signal: String,
    val weight: Double,
    val rawRisk: Double,
    val contribution: Double,
    val reason: String,
    val location: LocationBox?,
)

data class RiskResult(
    val score: Int,
    val level: String, // LOW_RISK | MEDIUM_RISK | HIGH_RISK
    val decision: String, // CLEAR | MANUAL_REVIEW
    val topReason: String,
    val breakdown: List<RiskSignalBreakdown>,
)

data class RegistryHit(
    val documentNumber: String,
    val fullName: String,
    val registryReason: String,
    val severity: String,
    val matchType: String, // EXACT | FUZZY — never collapsed into one flag
    val confidence: Double,
)

data class OcrResult(
    val documentType: String,
    val fields: Map<String, String>,
    val ocrConfidence: Double,
)

data class ValidationFinding(
    val check: String,
    val status: String, // PASS | FAIL
    val severity: String, // LOW | MEDIUM | HIGH
    val reason: String,
)

data class ValidationResult(
    val status: String, // PASS | FAIL
    val findings: List<ValidationFinding>,
)

data class TamperingResult(
    val tamperingRisk: Double,
    val findings: List<TamperingFindingItem>,
)

data class TamperingFindingItem(
    val type: String,
    val confidence: Double,
    val reason: String,
)

data class FaceMatchResult(
    val match: Boolean,
    val similarity: Double,
    val confidence: Double,
    val reason: String,
)

data class IdentityClusterMember(
    val recordId: String,
    val referenceName: String,
    val documentNumber: String?,
)

data class IdentityGraphResult(
    val status: String, // CLUSTER_FOUND | NO_CLUSTER
    val clusterSize: Int,
    val members: List<IdentityClusterMember>,
    val reason: String,
)

// The backend only tracks CLEARED/DISPUTED (see /verification/{id}/clear and
// /dispute) — "Further review" in the officer-facing UI is the same
// dispute action framed as a flag for secondary inspection, not a third
// backend state that doesn't actually exist.
enum class ScreeningStatus { PENDING, CLEARED, DISPUTED }

data class ScreeningQueueItem(
    val id: String,
    val travelerName: String,
    val documentType: String,
    val nationality: String,
    val checkpoint: String,
    val submittedAt: Long,
    val status: ScreeningStatus,
    val risk: RiskResult?,
    val registryHits: List<RegistryHit>,
    // Absolute path to the real front-document JPEG this screening was
    // submitted with, so the review screen can overlay real signal
    // bounding boxes on the real image. Null for the Phase-2 mock queue
    // items, which were never backed by an actual captured photo.
    val documentImagePath: String? = null,
    // Backend deepfake result. Real heuristic (ANALYZED) whenever a
    // screening was submitted through the app; null/NOT_IMPLEMENTED only
    // for the Phase-2 mock queue items, which predate this check.
    val deepfakeStatus: String? = null,
    val deepfakeReason: String? = null,
    // Backend liveness/anti-spoofing result — same real-vs-mock-item split
    // as deepfake above.
    val livenessStatus: String? = null,
    val livenessReason: String? = null,
    // Full per-signal detail returned by the real /documents/screen call,
    // used by the Extraction/Verification workflow steps. Null for the
    // Phase-2 mock items (never backed by a real backend call).
    val ocr: OcrResult? = null,
    val validation: ValidationResult? = null,
    val tampering: TamperingResult? = null,
    val face: FaceMatchResult? = null,
    val identityGraph: IdentityGraphResult? = null,
    // Officer decision metadata — set when the officer acts in the Review
    // step, not before. Never pre-filled with a manually chosen score.
    val officerNotes: String? = null,
    val decisionAt: Long? = null,
    val decidingOfficer: String? = null,
)

data class AuditLogEntry(
    val id: String,
    val timestamp: Long,
    val officer: String,
    val action: String,
    val record: String?,
    val result: String,
)

enum class AlertCategory {
    DOCUMENT_REVIEW_REQUIRED,
    RISK_ASSESSMENT_REVIEW,
    DUPLICATE_RECORD,
    INCOMPLETE_INFORMATION,
    VERIFICATION_REQUIRED,
}

data class AlertItem(
    val id: String,
    val category: AlertCategory,
    val screeningId: String,
    val travelerName: String,
    val description: String,
    val createdAt: Long,
    val status: ScreeningStatus,
)

data class OfficerProfile(
    val officerId: String,
    val role: String,
    val checkpoint: String,
    val lastLoginAt: Long?,
)
