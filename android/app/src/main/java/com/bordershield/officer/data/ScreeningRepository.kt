package com.bordershield.officer.data

import com.bordershield.officer.data.local.AuditLogStore
import com.bordershield.officer.data.local.LocalScreeningStore
import com.bordershield.officer.data.model.AlertCategory
import com.bordershield.officer.data.model.AlertItem
import com.bordershield.officer.data.model.AuditLogEntry
import com.bordershield.officer.data.model.OfficerProfile
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.data.model.ScreeningStatus
import com.bordershield.officer.data.remote.ApiService
import com.bordershield.officer.data.remote.AuditEventResponse
import com.bordershield.officer.data.remote.AuthSession
import com.bordershield.officer.data.remote.BlockchainVerifyRequest
import com.bordershield.officer.data.remote.BlockchainVerifyResponse
import com.bordershield.officer.data.remote.DisputeRequest
import com.bordershield.officer.data.remote.LoginRequest
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Local-cache-backed repository, plus the boundary to the real FastAPI
 * backend. The four Phase-2 mock queue items keep working locally
 * (dispute/clear on them will honestly fail against the backend — they were
 * never real verifications, and this doesn't fake a success for them); any
 * screening submitted through [submitScreening] is a real backend call.
 * Every officer action that matters (login, submit, decision, logout) is
 * appended to the real local [AuditLogStore] — nothing there is fabricated
 * after the fact. */
class ScreeningRepository(
    private val store: LocalScreeningStore,
    private val auditLog: AuditLogStore,
    private val api: ApiService,
    private val imagesDir: File,
    private val checkpoint: String,
) {
    fun observeQueue(): Flow<List<ScreeningQueueItem>> =
        store.observeAll().map { items -> items.sortedByDescending { it.submittedAt } }

    fun observeAuditLog(): Flow<List<AuditLogEntry>> =
        auditLog.observeAll().map { entries -> entries.sortedByDescending { it.timestamp } }

    /** High/medium-risk pending cases and cases with an identity-cluster hit
     * are surfaced as alerts — always derived from real queue state, never a
     * separately maintained (and possibly stale) list. */
    fun observeAlerts(): Flow<List<AlertItem>> = observeQueue().map { items ->
        items.mapNotNull { item -> toAlertOrNull(item) }.sortedByDescending { it.createdAt }
    }

    private fun toAlertOrNull(item: ScreeningQueueItem): AlertItem? {
        if (item.status != ScreeningStatus.PENDING) return null
        val risk = item.risk
        val category = when {
            risk != null && risk.level == "HIGH_RISK" -> AlertCategory.RISK_ASSESSMENT_REVIEW
            risk != null && risk.level == "MEDIUM_RISK" -> AlertCategory.RISK_ASSESSMENT_REVIEW
            item.identityGraph?.status == "CLUSTER_FOUND" -> AlertCategory.DUPLICATE_RECORD
            item.validation?.status == "FAIL" -> AlertCategory.VERIFICATION_REQUIRED
            item.ocr != null && item.ocr.fields.size < 2 -> AlertCategory.INCOMPLETE_INFORMATION
            else -> null
        } ?: return null
        val description = when (category) {
            AlertCategory.RISK_ASSESSMENT_REVIEW -> "Risk score ${risk?.score} (${risk?.level?.replace("_", " ")}) — ${risk?.topReason}"
            AlertCategory.DUPLICATE_RECORD -> item.identityGraph?.reason ?: "Duplicate identity signal detected"
            AlertCategory.VERIFICATION_REQUIRED -> "Document verification failed one or more checks"
            AlertCategory.INCOMPLETE_INFORMATION -> "Only ${item.ocr?.fields?.size ?: 0} field(s) extracted from the document"
            AlertCategory.DOCUMENT_REVIEW_REQUIRED -> "Document requires officer review"
        }
        return AlertItem(
            id = item.id,
            category = category,
            screeningId = item.id,
            travelerName = item.travelerName,
            description = description,
            createdAt = item.submittedAt,
            status = item.status,
        )
    }

    suspend fun getById(id: String): ScreeningQueueItem? = store.getById(id)

    /** Pulls the shared backend queue (every officer's screenings, not just
     * this device's) and adds any record this device hasn't seen yet.
     * Never overwrites a local record — a locally-submitted item already
     * has full per-signal detail that the list endpoint doesn't return,
     * and clobbering it would throw that away. Silently no-ops on failure
     * (offline/unreachable backend) rather than surfacing an error on
     * every screen load — callers that need to know can still call this
     * directly and catch. */
    suspend fun syncFromBackend() {
        try {
            val remote = api.listVerifications(AuthSession.bearerHeader())
            val existingIds = store.observeAll().first().map { it.id }.toSet()
            val newItems = remote.filter { it.id !in existingIds }.map { item ->
                ScreeningQueueItem(
                    id = item.id,
                    travelerName = item.travelerName ?: "(name not recorded)",
                    documentType = item.documentType,
                    nationality = item.nationality,
                    checkpoint = checkpoint,
                    submittedAt = parseTimestamp(item.createdAt),
                    status = when (item.status) {
                        "DISPUTED" -> ScreeningStatus.DISPUTED
                        "CLEARED" -> ScreeningStatus.CLEARED
                        else -> ScreeningStatus.PENDING
                    },
                    risk = com.bordershield.officer.data.model.RiskResult(
                        score = item.score,
                        level = item.level,
                        decision = item.decision,
                        topReason = "",
                        breakdown = emptyList(),
                    ),
                    registryHits = emptyList(),
                )
            }
            if (newItems.isNotEmpty()) store.upsertAll(newItems)
        } catch (_: Exception) {
            // Offline or backend unreachable — the local cache this device
            // already has is still shown; this just skips picking up
            // other officers' screenings for now.
        }
    }

    /** Fetches the full per-signal detail for one record from the backend
     * and merges it into the local copy — needed for an item that arrived
     * via [syncFromBackend] (list-only, no breakdown/ocr/etc.) when the
     * officer actually opens it. Throws on failure; caller shows the item
     * with whatever detail it already had. */
    suspend fun hydrateFullDetail(id: String) {
        val record = api.getVerification(AuthSession.bearerHeader(), id)
        val existing = store.getById(id) ?: return
        store.upsert(
            existing.copy(
                travelerName = record.travelerName ?: existing.travelerName,
                risk = record.risk,
                registryHits = record.registry?.hits ?: existing.registryHits,
                deepfakeStatus = record.deepfake?.status ?: existing.deepfakeStatus,
                deepfakeReason = record.deepfake?.reason ?: existing.deepfakeReason,
                livenessStatus = record.liveness?.status ?: existing.livenessStatus,
                livenessReason = record.liveness?.reason ?: existing.livenessReason,
                ocr = record.ocr ?: existing.ocr,
                validation = record.validation ?: existing.validation,
                tampering = record.tampering ?: existing.tampering,
                face = record.face ?: existing.face,
                identityGraph = record.identityGraph ?: existing.identityGraph,
            ),
        )
    }

    /** Real backend lifecycle trail for this record (CREATED/VIEWED/
     * DISPUTED/CLEARED, with the actual acting officer's username) —
     * distinct from the local device-only [observeAuditLog]. */
    suspend fun getBackendAuditTrail(id: String): List<AuditEventResponse> =
        api.getAuditTrail(AuthSession.bearerHeader(), id)

    /** Recomputes the mock hash chain up to this record's block and
     * confirms it's unbroken — a real integrity check, not a placeholder
     * "verified" badge. */
    suspend fun verifyBlockchain(id: String): BlockchainVerifyResponse =
        api.verifyBlockchain(AuthSession.bearerHeader(), BlockchainVerifyRequest(id))

    private fun parseTimestamp(iso: String): Long =
        try {
            OffsetDateTime.parse(iso).toInstant().toEpochMilli()
        } catch (_: Exception) {
            System.currentTimeMillis()
        }

    suspend fun findByTraveler(travelerName: String): List<ScreeningQueueItem> {
        val items = store.observeAll().first()
        return items.filter { it.travelerName.equals(travelerName, ignoreCase = true) }
            .sortedByDescending { it.submittedAt }
    }

    fun officerProfile(): OfficerProfile = OfficerProfile(
        officerId = AuthSession.username ?: "unknown",
        role = AuthSession.role ?: "OFFICER",
        checkpoint = checkpoint,
        lastLoginAt = AuthSession.loginAt,
    )

    suspend fun seedMockDataIfEmpty() {
        if (store.count() == 0) {
            store.upsertAll(MockScreenings.all)
        }
    }

    suspend fun login(username: String, password: String) {
        try {
            val response = api.login(LoginRequest(username, password))
            AuthSession.accessToken = response.accessToken
            AuthSession.username = username
            AuthSession.role = response.role
            AuthSession.loginAt = System.currentTimeMillis()
            logAudit(action = "Officer logged in", record = null, result = "SUCCESS")
        } catch (e: Exception) {
            logAudit(action = "Officer login attempt", record = null, result = "FAILED: ${e.message}", officerOverride = username)
            throw e
        }
    }

    suspend fun logout() {
        logAudit(action = "Officer logged out", record = null, result = "SUCCESS")
        AuthSession.clear()
    }

    /** Real call to POST /documents/screen. Throws on failure — the caller
     * surfaces the real error rather than fabricating a result, per the
     * project's no-faked-signal rule. */
    suspend fun submitScreening(
        travelerName: String,
        documentType: String,
        nationality: String,
        frontImageFile: File,
        liveImageFile: File?,
    ): ScreeningQueueItem {
        val frontPart = MultipartBody.Part.createFormData(
            "front_image", frontImageFile.name, frontImageFile.asRequestBody("image/jpeg".toMediaType()),
        )
        val livePart = liveImageFile?.let {
            MultipartBody.Part.createFormData("live_capture", it.name, it.asRequestBody("image/jpeg".toMediaType()))
        }
        val response = api.screenDocument(
            authorization = AuthSession.bearerHeader(),
            documentType = documentType.toRequestBody("text/plain".toMediaType()),
            nationality = nationality.toRequestBody("text/plain".toMediaType()),
            frontImage = frontPart,
            liveCapture = livePart,
        )
        val persistedImagePath = withContext(Dispatchers.IO) {
            val dest = File(imagesDir, "${response.verificationId}.jpg")
            frontImageFile.copyTo(dest, overwrite = true)
            dest.absolutePath
        }
        val item = ScreeningQueueItem(
            id = response.verificationId,
            travelerName = travelerName,
            documentType = documentType,
            nationality = nationality,
            checkpoint = checkpoint,
            submittedAt = System.currentTimeMillis(),
            status = ScreeningStatus.PENDING,
            risk = response.risk,
            registryHits = response.registry?.hits ?: emptyList(),
            documentImagePath = persistedImagePath,
            deepfakeStatus = response.deepfake?.status,
            deepfakeReason = response.deepfake?.reason,
            livenessStatus = response.liveness?.status,
            livenessReason = response.liveness?.reason,
            ocr = response.ocr,
            validation = response.validation,
            tampering = response.tampering,
            face = response.face,
            identityGraph = response.identityGraph,
        )
        store.upsert(item)
        logAudit(action = "Document scanned", record = item.id, result = "OCR + validation + risk assessment completed")
        logAudit(
            action = "Risk assessment generated",
            record = item.id,
            result = "score=${item.risk?.score} level=${item.risk?.level} decision=${item.risk?.decision}",
        )
        return item
    }

    /** Throws on failure (including a 404 for the Phase-2 mock items, which
     * have no real backend record) — caller must show the real error. */
    suspend fun disputeOnBackend(id: String, reason: String) {
        api.dispute(AuthSession.bearerHeader(), id, DisputeRequest(reason))
        store.getById(id)?.let {
            store.upsert(
                it.copy(
                    status = ScreeningStatus.DISPUTED,
                    officerNotes = reason,
                    decisionAt = System.currentTimeMillis(),
                    decidingOfficer = AuthSession.username,
                ),
            )
        }
        logAudit(action = "Decision submitted: FLAG / FURTHER REVIEW", record = id, result = "reason=\"$reason\"")
    }

    suspend fun clearOnBackend(id: String, notes: String?) {
        api.clear(AuthSession.bearerHeader(), id)
        store.getById(id)?.let {
            store.upsert(
                it.copy(
                    status = ScreeningStatus.CLEARED,
                    officerNotes = notes,
                    decisionAt = System.currentTimeMillis(),
                    decidingOfficer = AuthSession.username,
                ),
            )
        }
        logAudit(action = "Decision submitted: CLEAR", record = id, result = notes?.let { "notes=\"$it\"" } ?: "no notes")
    }

    suspend fun logTourCompleted() {
        logAudit(action = "Guided tour completed", record = null, result = "SUCCESS")
    }

    private suspend fun logAudit(action: String, record: String?, result: String, officerOverride: String? = null) {
        auditLog.append(
            AuditLogEntry(
                id = UUID.randomUUID().toString(),
                timestamp = System.currentTimeMillis(),
                officer = officerOverride ?: AuthSession.username ?: "unknown",
                action = action,
                record = record,
                result = result,
            ),
        )
    }
}
