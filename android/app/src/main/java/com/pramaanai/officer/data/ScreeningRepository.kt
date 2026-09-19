package com.pramaanai.officer.data

import com.pramaanai.officer.data.local.AuditLogStore
import com.pramaanai.officer.data.local.LocalScreeningStore
import com.pramaanai.officer.data.local.PendingSubmissionQueue
import com.pramaanai.officer.data.model.AlertCategory
import com.pramaanai.officer.data.model.AlertItem
import com.pramaanai.officer.data.model.AuditLogEntry
import com.pramaanai.officer.data.model.OfficerProfile
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.data.remote.ApiService
import com.pramaanai.officer.data.remote.AuditEventResponse
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.data.remote.RefreshRequest
import com.pramaanai.officer.data.remote.SessionEvents
import com.pramaanai.officer.data.remote.BlockchainVerifyRequest
import com.pramaanai.officer.data.remote.BlockchainVerifyResponse
import com.pramaanai.officer.data.remote.CaseDecisionRequest
import com.pramaanai.officer.data.remote.CaseSubmitRequest
import com.pramaanai.officer.data.remote.DisputeRequest
import com.pramaanai.officer.data.remote.LoginRequest
import com.pramaanai.officer.data.remote.ScreeningSubmissionRequest
import java.io.File
import java.io.IOException
import java.time.OffsetDateTime
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import retrofit2.HttpException

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
    private val pendingQueue: PendingSubmissionQueue,
) {
    // Prefers the real, server-assigned checkpoint (populated at login —
    // see login() below) over the constructor default, which only ever
    // applies pre-login or if /auth/me returned none.
    private val effectiveCheckpoint: String
        get() = AuthSession.checkpointName ?: checkpoint

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
                    checkpoint = effectiveCheckpoint,
                    submittedAt = parseTimestamp(item.createdAt),
                    status = when (item.status) {
                        "DISPUTED" -> ScreeningStatus.DISPUTED
                        "CLEARED" -> ScreeningStatus.CLEARED
                        else -> ScreeningStatus.PENDING
                    },
                    risk = com.pramaanai.officer.data.model.RiskResult(
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
        role = AuthSession.role ?: "FIELD_OFFICER",
        checkpoint = effectiveCheckpoint,
        lastLoginAt = AuthSession.loginAt,
    )

    suspend fun seedMockDataIfEmpty() {
        if (store.count() == 0) {
            store.upsertAll(MockScreenings.all)
        }
    }

    /** GET /checkpoints is public (no auth needed) — used by the login
     * screen's checkpoint dropdown before the officer has a token. */
    suspend fun listCheckpoints() = api.listCheckpoints()

    /** [selectedCheckpointCode] is what the officer picked on the login
     * screen. The backend's checkpoint assignment (set by IT/Admin, via
     * /auth/me) is the only one that's ever actually used for
     * screening/case creation — this is purely an honesty check so the
     * login screen never shows a checkpoint the account isn't really
     * assigned to: a mismatch fails the login rather than silently
     * proceeding under the selected (wrong) one. */
    suspend fun login(username: String, password: String, selectedCheckpointCode: String?) {
        try {
            val response = api.login(LoginRequest(username, password))
            AuthSession.accessToken = response.accessToken
            AuthSession.refreshToken = response.refreshToken
            AuthSession.username = username
            AuthSession.role = response.role
            AuthSession.loginAt = System.currentTimeMillis()

            val me = api.getCurrentUser(AuthSession.bearerHeader())
            AuthSession.checkpointCode = me.checkpointCode
            AuthSession.checkpointName = me.checkpointName

            if (selectedCheckpointCode != null && me.checkpointCode != null && selectedCheckpointCode != me.checkpointCode) {
                AuthSession.clear()
                throw IllegalStateException(
                    "You selected $selectedCheckpointCode, but this account is assigned to " +
                        "${me.checkpointName} (${me.checkpointCode}).",
                )
            }

            AuthSession.persist()
            SessionEvents.pendingNotice = null
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

    /** Exchanges the stored refresh token for a fresh pair. Backs both the
     * "Stay signed in" button (a real server-side renewal, not just a
     * local idle-timer reset) and the silent check at app launch after a
     * restored session. A rejected refresh token ends the session; a
     * network failure leaves it untouched so an offline officer isn't
     * kicked out. */
    suspend fun refreshSession() {
        val refresh = AuthSession.refreshToken ?: return
        try {
            val tokens = api.refresh(RefreshRequest(refresh))
            AuthSession.updateTokens(tokens.accessToken, tokens.refreshToken)
        } catch (e: HttpException) {
            if (e.code() == 401) SessionEvents.expire("Your session has expired. Please sign in again.")
        } catch (_: IOException) {
            // offline — keep the session, try again on the next call
        }
    }

    /** The Render free-tier backend sleeps after ~15 min idle; a request
     * that arrives while it's still waking up gets a fast 503 from Render's
     * own edge proxy (not a hang — no client timeout would help). Retries
     * with backoff give the ~10-30s wake-up window time to finish rather
     * than surfacing that as a submission failure. Any other error (4xx,
     * a real 5xx from the app itself, no network) is not retried and is
     * thrown straight through — a real failure stays a real failure. */
    private suspend fun <T> callScreeningWithRetry(call: suspend () -> T): T {
        val delaysMs = listOf(8_000L, 20_000L)
        delaysMs.forEachIndexed { attempt, delayMs ->
            try {
                return call()
            } catch (e: HttpException) {
                if (e.code() != 503) throw e
                if (attempt == delaysMs.lastIndex) throw e
                delay(delayMs)
            }
        }
        return call()
    }

    /** Real call to POST /documents/screen — JSON body only (see
     * ApiService.screenDocument / ScreeningSubmissionRequest): OCR fields,
     * MRZ text, and two face-embedding vectors, all extracted on-device
     * by [com.pramaanai.officer.data.vision.DocumentOcrExtractor] and
     * [com.pramaanai.officer.data.vision.FaceEmbedding] before this call —
     * raw images never cross the wire. [documentImageFile], if provided,
     * is copied to on-device storage purely for this officer's own later
     * reference in the review screen (CLAUDE.md: images "stay local for
     * the officer's own reference") — it is never sent to the server.
     *
     * On a genuine connectivity failure (no route to the backend at all —
     * an [IOException], not a real HTTP error response), this queues the
     * submission in [pendingQueue] instead of throwing, matching
     * CLAUDE.md's "never block the officer on a missing connection." A
     * real server-side rejection (4xx/5xx — an [HttpException]) is NOT
     * queued; it's a genuine failure and is thrown straight through. */
    suspend fun submitScreening(
        travelerName: String,
        documentType: String,
        nationality: String,
        ocrFields: Map<String, String>,
        ocrConfidence: Double,
        mrzText: String?,
        documentFaceEmbedding: List<Float>?,
        liveFaceEmbedding: List<Float>?,
        documentImageFile: File? = null,
        documentBackImageFile: File? = null,
        selfieImageFile: File? = null,
        faceDetectionResult: com.pramaanai.officer.data.model.FaceDetectionResult? = null,
    ): ScreeningQueueItem {
        val request = ScreeningSubmissionRequest(
            documentType = documentType,
            nationality = nationality,
            ocrFields = ocrFields,
            ocrConfidence = ocrConfidence,
            mrzText = mrzText,
            documentFaceEmbedding = documentFaceEmbedding,
            liveFaceEmbedding = liveFaceEmbedding,
            faceDetectionResult = faceDetectionResult,
        )

        val response = try {
            callScreeningWithRetry { api.screenDocument(AuthSession.bearerHeader(), request) }
        } catch (e: IOException) {
            pendingQueue.enqueue(travelerName, request)
            logAudit(
                action = "Screening queued (offline)",
                record = null,
                result = "documentType=$documentType nationality=$nationality — will sync when connectivity returns",
            )
            return ScreeningQueueItem(
                id = UUID.randomUUID().toString(),
                travelerName = travelerName,
                documentType = documentType,
                nationality = nationality,
                checkpoint = effectiveCheckpoint,
                submittedAt = System.currentTimeMillis(),
                status = ScreeningStatus.OFFLINE_QUEUED,
                risk = null,
                registryHits = emptyList(),
            ).also { store.upsert(it) }
        }

        val persistedImagePath = documentImageFile?.let { file ->
            withContext(Dispatchers.IO) {
                val dest = File(imagesDir, "${response.verificationId}.jpg")
                file.copyTo(dest, overwrite = true)
                dest.absolutePath
            }
        }
        val persistedBackImagePath = documentBackImageFile?.let { file ->
            withContext(Dispatchers.IO) {
                val dest = File(imagesDir, "${response.verificationId}_back.jpg")
                file.copyTo(dest, overwrite = true)
                dest.absolutePath
            }
        }
        val persistedSelfiePath = selfieImageFile?.let { file ->
            withContext(Dispatchers.IO) {
                val dest = File(imagesDir, "${response.verificationId}_selfie.jpg")
                file.copyTo(dest, overwrite = true)
                dest.absolutePath
            }
        }
        val item = screeningResponseToQueueItem(
            response, travelerName, documentType, nationality, effectiveCheckpoint, persistedImagePath, persistedBackImagePath, persistedSelfiePath, mrzText,
        )
        store.upsert(item)
        logAudit(action = "Document scanned", record = item.id, result = "on-device OCR + MRZ + embedding extraction, server-side validation + risk assessment completed")
        logAudit(
            action = "Risk assessment generated",
            record = item.id,
            result = "score=${item.risk?.score} level=${item.risk?.level} decision=${item.risk?.decision}",
        )
        return item
    }

    /** Forwards this device's case to the Immigration Officer's queue on
     * the web console (POST /cases/{caseId}/submit) — the actual Clear /
     * Secondary Review / Hold-Refer decision happens there, not on this
     * device (see CLAUDE.md: a Field Officer sends cases, an Immigration
     * Officer decides them). Throws on failure — including for the
     * Phase-2 mock queue items, which have no real caseId. */
    suspend fun sendCaseToImmigration(id: String, note: String?) {
        val queueItem = store.getById(id) ?: error("Unknown screening: $id")
        val caseId = queueItem.caseId ?: error("This screening has no backend case to forward (mock/offline item).")
        api.submitCase(AuthSession.bearerHeader(), caseId, CaseSubmitRequest(note))
        store.upsert(queueItem.copy(status = ScreeningStatus.SENT, officerNotes = note ?: queueItem.officerNotes))
        logAudit(action = "Case forwarded to Immigration Officer", record = id, result = note?.let { "notes=\"$it\"" } ?: "no notes")
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

    /** Make a formal case decision (Clear/Secondary Review/Hold Refer) through the case API.
     * This is the preferred method over the older verification-level clear/dispute. */
    suspend fun decideCaseOnBackend(id: String, decision: String, reason: String?) {
        val queueItem = store.getById(id) ?: error("Unknown screening: $id")
        val caseId = queueItem.caseId ?: error("This screening has no backend case to decide (mock/offline item).")

        api.decideCase(
            AuthSession.bearerHeader(),
            caseId,
            CaseDecisionRequest(decision = decision, reason = reason)
        )

        val newStatus = when (decision) {
            "CLEAR" -> ScreeningStatus.CLEARED
            "SECONDARY_REVIEW" -> ScreeningStatus.DISPUTED
            "HOLD_REFER" -> ScreeningStatus.DISPUTED
            else -> queueItem.status
        }

        store.upsert(
            queueItem.copy(
                status = newStatus,
                officerNotes = reason ?: queueItem.officerNotes,
                decisionAt = System.currentTimeMillis(),
                decidingOfficer = AuthSession.username,
            )
        )

        val actionDescription = when (decision) {
            "CLEAR" -> "Decision submitted: CLEAR"
            "SECONDARY_REVIEW" -> "Decision submitted: SECONDARY REVIEW"
            "HOLD_REFER" -> "Decision submitted: HOLD/REFER"
            else -> "Decision submitted: $decision"
        }

        logAudit(
            action = actionDescription,
            record = id,
            result = reason?.let { "reason=\"$it\"" } ?: "no reason"
        )
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
