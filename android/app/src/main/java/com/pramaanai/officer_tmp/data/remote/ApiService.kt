package com.bordershield.officer.data.remote

import com.bordershield.officer.data.model.FaceMatchResult
import com.bordershield.officer.data.model.IdentityGraphResult
import com.bordershield.officer.data.model.OcrResult
import com.bordershield.officer.data.model.RegistryHit
import com.bordershield.officer.data.model.RiskResult
import com.bordershield.officer.data.model.TamperingResult
import com.bordershield.officer.data.model.ValidationResult
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
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

    @Multipart
    @POST("documents/screen")
    suspend fun screenDocument(
        @Header("Authorization") authorization: String,
        @Part("document_type") documentType: RequestBody,
        @Part("nationality") nationality: RequestBody,
        @Part frontImage: MultipartBody.Part,
        @Part liveCapture: MultipartBody.Part?,
    ): ScreeningResponse

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
}

data class LoginRequest(val username: String, val password: String)

data class TokenResponse(
    val accessToken: String,
    val refreshToken: String,
    val tokenType: String,
    val role: String,
    val username: String? = null,
)

data class DisputeRequest(val reason: String)

data class ScreeningResponse(
    val verificationId: String,
    val risk: RiskResult,
    val ocr: OcrResult?,
    val validation: ValidationResult?,
    val tampering: TamperingResult?,
    val registry: RegistryLookupResult?,
    val deepfake: DeepfakeResult?,
    val liveness: LivenessResult?,
    val face: FaceMatchResult?,
    val identityGraph: IdentityGraphResult?,
)

data class RegistryLookupResult(val status: String, val hits: List<RegistryHit>)

data class DeepfakeResult(val status: String, val score: Double?, val reason: String)

data class LivenessResult(val status: String, val score: Double?, val reason: String)

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

data class CurrentUserResponse(val id: String, val username: String, val role: String)
