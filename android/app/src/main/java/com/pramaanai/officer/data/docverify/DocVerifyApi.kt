package com.pramaanai.officer.data.docverify

import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

/** /api/v1 screening + document verification (see app/api/routes/verify_v1.py).
 * The device sends REGION CROPS located by its on-board YOLO11n detector —
 * never the full document image — plus the text its own OCR read. Field
 * names are camelCase here and become snake_case on the wire via
 * RetrofitClient's Gson naming policy. Everything the server may omit is
 * nullable: Gson does not enforce Kotlin null-safety. */
interface DocVerifyApi {
    @POST("api/v1/verify/regions")
    suspend fun verifyRegions(
        @Header("Authorization") authorization: String,
        @Body request: RegionVerificationRequest,
    ): VerificationOutcome

    @POST("api/v1/verification/{id}/officer-action")
    suspend fun officerAction(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
        @Body request: OfficerActionRequest,
    ): VerificationListItem

    @GET("api/v1/verification")
    suspend fun listMine(
        @Header("Authorization") authorization: String,
        @Query("mine") mine: Boolean = true,
        @Query("limit") limit: Int = 100,
    ): List<VerificationListItem>

    @GET("api/v1/verification/{id}")
    suspend fun get(
        @Header("Authorization") authorization: String,
        @Path("id") verificationId: String,
    ): VerificationEnvelope
}

data class RegionCrop(
    val label: String,
    val bbox: List<Int>,
    val cropBbox: List<Int>,
    val confidence: Float,
    val imageB64: String,
)

data class RegionDocument(
    val imageSize: List<Int>,
    val regions: List<RegionCrop>,
    val deviceDetector: String?,
)

/** A line of text read by the phone's ML Kit OCR, in original-image pixels. */
data class DeviceTextLine(
    val documentIndex: Int,
    val text: String,
    val bbox: List<Int>,
    val confidence: Float,
)

/** One HTTPS request carries every crop of the capture. [clientRequestId]
 * makes retries idempotent: a re-sent offline item returns the stored result
 * (and the same screening case). */
data class RegionVerificationRequest(
    val documents: List<RegionDocument>,
    val clientRequestId: String? = null,
    val liveFaceB64: String? = null,
    val borderRoute: String? = null,
    val direction: String? = null,
    val declaredNationality: String? = null,
    val capturedOffline: Boolean = false,
    val deviceId: String? = null,
    val capturedAt: String? = null,
    val expectedDocumentType: String? = null,
    // Nullable: items queued by an older app version were stored without it.
    val deviceText: List<DeviceTextLine>? = null,
    val openCase: Boolean = false,
)

data class OfficerActionRequest(val action: String, val reason: String?)

data class VerificationListItem(
    val id: String,
    val sequence: Int? = null,
    val createdAt: String? = null,
    val documentTypes: List<String>? = null,
    val country: String? = null,
    val borderRoute: String? = null,
    val overallStatus: String,
    val riskScore: Int? = null,
    val riskLevel: String? = null,
    val officerAction: String,
    val syncStatus: String? = null,
    val capturedOffline: Boolean? = null,
    val caseId: String? = null,
    val caseNumber: String? = null,
    val caseStatus: String? = null,
    val reviewerResponded: Boolean? = null,
    val lastUpdateAt: String? = null,
    val attentionChecks: List<String>? = null,
)

data class VerificationEnvelope(
    val record: VerificationListItem,
    val result: VerificationOutcome,
)

data class OfficerLine(val icon: String, val text: String)

data class OfficerSummary(
    val headline: String,
    val facts: Map<String, String>?,
    val lines: List<OfficerLine>?,
    val responsibilityNotice: String?,
)

data class EvidenceItem(
    val id: String,
    val check: String,
    val description: String,
    val bbox: List<Int>?,
    val documentIndex: Int?,
)

data class CheckDetail(
    val name: String,
    val status: String,
    val summary: String,
    val blocking: Boolean,
    val evidenceIds: List<String>?,
    val documentIndex: Int?,
    val details: Map<String, Any?>? = null,
)

data class FieldValue(val value: String, val confidence: Double, val source: String)

data class DocumentTypeResult(val documentType: String, val country: String?, val confidence: Double)

data class StampInfo(
    val stampType: String?,
    val identification: String?,
    val country: String?,
    val checkpoint: String?,
    val direction: String?,
    val date: String?,
    val bbox: List<Int>?,
)

data class DocumentAnalysis(
    val documentIndex: Int,
    val imageSize: List<Int>?,
    val documentType: DocumentTypeResult,
    val fields: Map<String, FieldValue>?,
    val stamps: List<StampInfo>? = null,
)

data class CaseDecision(val decision: String, val reason: String?, val at: String?, val username: String?, val role: String?)

data class CaseNote(val note: String, val at: String?, val username: String?, val role: String?)

/** The screening case this verification opened (status, reviewer responses). */
data class CaseInfo(
    val caseId: String? = null,
    val caseNumber: String? = null,
    val screeningVerificationId: String? = null,
    val status: String? = null,
    val priority: String? = null,
    val sentAt: String? = null,
    val decidedAt: String? = null,
    val decisions: List<CaseDecision>? = null,
    val notes: List<CaseNote>? = null,
    val reason: String? = null,
)

data class ClusterMember(val recordId: String?, val referenceName: String?, val documentNumber: String?)

data class FaceCluster(val status: String, val clusterSize: Int, val members: List<ClusterMember>?, val reason: String?)

data class DuplicateDocument(val status: String, val matchCount: Int, val reason: String?)

data class IdentityInfo(
    val faceCluster: FaceCluster? = null,
    val duplicateDocument: DuplicateDocument? = null,
    val notes: List<String>? = null,
)

data class RiskPart(val check: String, val status: String?, val points: Int, val reason: String)

data class VerificationOutcome(
    val id: String?,
    val overallStatus: String,
    val country: String?,
    val documentType: String,
    val explanation: String?,
    val riskScore: Int,
    val riskLevel: String,
    val riskBreakdown: List<RiskPart>? = null,
    val confidence: Double,
    val checks: Map<String, String>?,
    val checkDetails: List<CheckDetail>,
    val evidence: List<EvidenceItem>?,
    val documents: List<DocumentAnalysis>,
    val officerSummary: OfficerSummary,
    val dataNotice: String?,
    val suggestedReasons: Map<String, String>? = null,
    val case: CaseInfo? = null,
    val identity: IdentityInfo? = null,
    val generatedAt: String? = null,
)
