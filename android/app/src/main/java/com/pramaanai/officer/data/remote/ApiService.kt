package com.pramaanai.officer.data.remote

import com.pramaanai.officer.data.model.FaceDetectionResult
import com.pramaanai.officer.data.model.FaceMatchResult
import com.pramaanai.officer.data.model.IdentityGraphResult
import com.pramaanai.officer.data.model.OcrResult
import com.pramaanai.officer.data.model.RegistryHit
import com.pramaanai.officer.data.model.RiskResult
import com.pramaanai.officer.data.model.TamperingResult
import com.pramaanai.officer.data.model.ValidationResult
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** Matches the FastAPI backend's real endpoints (see the routes under
 * ../../../../../../app/api/routes). Field names on the response DTOs are
 * plain camelCase — RetrofitClient's Gson instance is configured with
 * LOWER_CASE_WITH_UNDERSCORES field naming to match the backend's snake_case
 * JSON without needing @SerializedName on every property. */
interface ApiService {
    @POST("auth/login")
    suspend fun login(@Body request: LoginRequest): TokenResponse

    @POST("auth/refresh")
    suspend fun refresh(@Body request: RefreshRequest): TokenResponse

    // JSON only — matches the backend's ScreeningSubmission exactly (see
    // app/schemas/verification.py). The device sends *extracted* data
    // only (OCR fields, MRZ text, two on-device face-embedding vectors);
    // raw document/selfie images never leave the device, never cross
    // this call.
    @POST("documents/screen")
    suspend fun screenDocument(
        @Header("Authorization") authorization: String,
        @Body request: ScreeningSubmissionRequest,
    ): ScreeningResponse

    @POST("cases/{id}/submit")
    suspend fun submitCase(
        @Header("Authorization") authorization: String,
        @Path("id") caseId: String,
        @Body request: CaseSubmitRequest,
    ): CaseListItemResponse

    @POST("verification/{id}/dispute")
    suspend fun dispute(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
        @Body request: DisputeRequest,
    )

    @POST("verification/{id}/clear")
    suspend fun clear(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
    )

    @POST("cases/{id}/decision")
    suspend fun decideCase(
        @Header("Authorization") authorization: String,
        @Path("id") caseId: String,
        @Body request: CaseDecisionRequest,
    ): CaseDetailResponse

    @GET("verification")
    suspend fun listVerifications(
        @Header("Authorization") authorization: String,
        @Query("limit") limit: Int = 100,
        @Query("offset") offset: Int = 0,
    ): List<VerificationListItemResponse>

    @GET("verification/{id}")
    suspend fun getVerification(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
    ): VerificationRecordResponse

    @GET("verification/{id}/audit")
    suspend fun getAuditTrail(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
    ): List<AuditEventResponse>

    @POST("blockchain/verify")
    suspend fun verifyBlockchain(
        @Header("Authorization") authorization: String,
        @Body request: BlockchainVerifyRequest,
    ): BlockchainVerifyResponse

    @GET("auth/me")
    suspend fun getCurrentUser(@Header("Authorization") authorization: String): CurrentUserResponse

    // Public — no auth header. Used by the login screen's checkpoint
    // dropdown before the officer has a token.
    @GET("checkpoints")
    suspend fun listCheckpoints(): List<CheckpointResponse>

    // Public liveness check (GET /health at the app root, not
    // /system/health which is IT_ADMIN-only) — used by
    // ConnectivityMonitor for the real Online/Weak/Offline check.
    @GET("health")
    suspend fun health(): Map<String, String>
}

data class CheckpointResponse(
    val id: String,
    val code: String,
    val name: String,
    val location: String?,
    val isActive: Boolean,
)

data class LoginRequest(val username: String, val password: String)

data class RefreshRequest(val refreshToken: String)

data class TokenResponse(
    val accessToken: String,
    val refreshToken: String,
    val tokenType: String,
    val role: String,
    val username: String? = null,
)

// Mirrors app/schemas/verification.py's ScreeningSubmission field-for-field
// (Gson's LOWER_CASE_WITH_UNDERSCORES policy maps documentType ->
// document_type, etc.). tampering/deepfake/liveness stay null this pass —
// those need pixel-level analysis, which isn't built on-device yet; the
// backend's risk engine already treats a missing signal as "not run",
// never as "clean" (see app/services/risk/engine.py).
data class ScreeningSubmissionRequest(
    val documentType: String,
    val nationality: String,
    val ocrFields: Map<String, String>,
    val ocrConfidence: Double,
    val mrzText: String?,
    val aadhaarNumber: String? = null,
    val documentFaceEmbedding: List<Float>?,
    val liveFaceEmbedding: List<Float>?,
    val tamperingResult: TamperingResult? = null,
    val deepfakeResult: DeepfakeResult? = null,
    val livenessResult: LivenessResult? = null,
    // On-device ML Kit face detection over the live selfie (see
    // FaceDetectionAnalyzer.kt) — face count/position, never the image.
    val faceDetectionResult: FaceDetectionResult? = null,
)

data class DisputeRequest(val reason: String)

data class CaseSubmitRequest(val note: String? = null)

data class CaseListItemResponse(
    val id: String,
    val caseNumber: String,
    val status: String,
)

data class DuplicateDocumentResult(
    val status: String, // NO_MATCH | SAME_IDENTITY_REUSE | DIFFERENT_IDENTITY_REUSE
    val matchCount: Int,
    val reason: String,
)

data class CitizenRegistryResult(
    val status: String, // MATCH | MISMATCH | NO_RECORD | REVOKED_MATCH
    val reason: String,
    val mismatchedFields: List<String> = emptyList(),
)

data class ScreeningResponse(
    val verificationId: String,
    val caseId: String,
    val caseNumber: String,
    val caseStatus: String,
    val risk: RiskResult,
    val ocr: OcrResult?,
    val validation: ValidationResult?,
    val tampering: TamperingResult?,
    val registry: RegistryLookupResult?,
    val deepfake: DeepfakeResult?,
    val liveness: LivenessResult?,
    val face: FaceMatchResult?,
    val identityGraph: IdentityGraphResult?,
    val faceDetection: FaceDetectionResult? = null,
    val duplicateDocument: DuplicateDocumentResult? = null,
    val citizenRegistry: CitizenRegistryResult? = null,
)

data class RegistryLookupResult(val status: String, val hits: List<RegistryHit>)

data class DeepfakeResult(val status: String, val score: Double?, val reason: String)

// Matches app/services/liveness/base.py LivenessResult exactly
data class LivenessResult(
    val status: String,  // LIVE | SUSPECTED_SPOOF | NOT_IMPLEMENTED | UNCERTAIN
    val score: Double?,  // Spoof risk 0.0-1.0 (higher = more suspicious)
    val reason: String
)

data class VerificationListItemResponse(
    val id: String,
    val documentType: String,
    val nationality: String,
    val travelerName: String?,
    val score: Int,
    val level: String,
    val decision: String,
    val status: String,
    val createdAt: String,
)

data class VerificationRecordResponse(
    val id: String,
    val documentType: String,
    val nationality: String,
    val travelerName: String?,
    val risk: RiskResult,
    val signatureValid: Boolean,
    val createdAt: String,
    val ocr: OcrResult?,
    val validation: ValidationResult?,
    val tampering: TamperingResult?,
    val deepfake: DeepfakeResult?,
    val registry: RegistryLookupResult?,
    val face: FaceMatchResult?,
    val identityGraph: IdentityGraphResult?,
    val liveness: LivenessResult?,
    val faceDetection: FaceDetectionResult? = null,
    val duplicateDocument: DuplicateDocumentResult? = null,
    val citizenRegistry: CitizenRegistryResult? = null,
)

data class AuditEventResponse(
    val id: String,
    val eventType: String,
    val actorUserId: String,
    val actorUsername: String?,
    val reason: String?,
    val createdAt: String,
)

data class BlockchainVerifyRequest(val verificationId: String)

data class BlockchainVerifyResponse(
    val verificationId: String,
    val chainValid: Boolean,
    val record: Map<String, Any?>?,
)

data class CurrentUserResponse(
    val id: String,
    val username: String,
    val role: String,
    val checkpointId: String?,
    val checkpointCode: String?,
    val checkpointName: String?,
)

data class CaseDecisionRequest(
    val decision: String, // "CLEAR", "SECONDARY_REVIEW", "HOLD_REFER"
    val reason: String? = null,
)

data class CaseDetailResponse(
    val id: String,
    val caseNumber: String,
    val status: String,
    val priority: String,
    val checkpointCode: String,
    val fieldOfficerUsername: String,
    val assignedOfficerUsername: String?,
    val documentType: String,
    val nationality: String,
    val travelerName: String?,
    val createdAt: String,
    val sentAt: String?,
    val decidedAt: String?,
    val verification: VerificationRecordResponse?,
    val notes: List<CaseNoteResponse>,
    val decisions: List<CaseDecisionSummary>,
)

data class CaseNoteResponse(
    val id: String,
    val authorUsername: String,
    val note: String,
    val createdAt: String,
)

data class CaseDecisionSummary(
    val decision: String,
    val officerUsername: String?,
    val reason: String?,
    val createdAt: String,
)
