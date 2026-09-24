package com.pramaanai.officer.data.docverify

import android.content.Context
import android.graphics.Bitmap
import android.provider.Settings
import com.pramaanai.officer.data.connectivity.ConnectivityMonitor
import com.pramaanai.officer.data.connectivity.ConnectivityState
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.data.remote.RetrofitClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import java.time.Instant
import kotlin.math.max

/** Officer workflow for document verification:
 *   capture -> on-device YOLO11n region detection -> padded region crops
 *   -> live connectivity check -> ONLINE: POST /api/v1/verify/regions
 *                               -> OFFLINE/WEAK: encrypted queue + local checks
 * The full document image never leaves the phone. */
class DocVerifyRepository(private val context: Context) {

    data class Analysis(
        val bitmap: Bitmap,
        val detections: List<OnDeviceRegionDetector.Detection>,
        val detectorAvailable: Boolean,
        val localChecks: List<LocalCheck>,
        val text: RegionCropper.OnDeviceText = RegionCropper.OnDeviceText(emptyList(), emptyList()),
        val mrzFields: Map<String, String> = emptyMap(),
    )

    /** Live selfie → a tight face crop only (the full selfie never leaves the phone). */
    sealed class Selfie {
        /** [passiveScore]: MiniFASNet "real person" probability on the full frame (null if unavailable). */
        data class Face(val crop: Bitmap, val passiveScore: Float? = null) : Selfie()
        data class Problem(val message: String) : Selfie()
    }

    sealed class Submission {
        data class Verified(val outcome: VerificationOutcome) : Submission()
        data class Queued(val localChecks: List<LocalCheck>, val reason: String) : Submission()
        data class Failed(val message: String) : Submission()
    }

    private val connectivity = ConnectivityMonitor(context, RetrofitClient.apiService)

    companion object {
        /** Outlives the screen, so an evidence upload finishes after navigation. */
        private val background = kotlinx.coroutines.CoroutineScope(kotlinx.coroutines.SupervisorJob() + Dispatchers.IO)
    }

    suspend fun analyze(source: Bitmap): Analysis = withContext(Dispatchers.Default) {
        val bitmap = downscale(source, 2000)
        val detector = OnDeviceRegionDetector.get(context)
        val detections = detector?.detect(bitmap) ?: emptyList()
        val text = RegionCropper.readText(bitmap)
        val mrzLines = text.lines.map { it.text.uppercase().replace(" ", "").replace("«", "<<") }
            .filter { it.length >= 28 && it.count { c -> c == '<' } >= 2 }.takeLast(2)
        Analysis(bitmap, detections, detector != null, RegionCropper.localChecks(bitmap, detections), text,
            if (mrzLines.size == 2 && mrzLines[0].startsWith("P")) MrzCheck.fields(mrzLines) else emptyMap())
    }

    suspend fun selfieFace(source: Bitmap): Selfie = withContext(Dispatchers.Default) {
        val bitmap = downscale(source, 1280)
        val faces = runCatching { com.pramaanai.officer.data.vision.FaceDetectionAnalyzer.detect(bitmap).faces }
            .getOrElse { return@withContext Selfie.Problem(com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_face_detection_unavailable)) }
        when {
            faces.isEmpty() -> Selfie.Problem(com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_no_face))
            faces.size > 1 -> Selfie.Problem(com.pramaanai.officer.ui.i18n.L.f(com.pramaanai.officer.R.string.rp_many_faces, faces.size))
            faces[0].touchesEdge -> Selfie.Problem(com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_face_cut_off))
            else -> {
                val b = faces[0].location
                val m = (0.25f * maxOf(b.width, b.height)).toInt()
                val l = (b.x - m).coerceAtLeast(0)
                val t = (b.y - m).coerceAtLeast(0)
                val r = (b.x + b.width + m).coerceAtMost(bitmap.width)
                val btm = (b.y + b.height + m).coerceAtMost(bitmap.height)
                val passive = com.pramaanai.officer.data.vision.PassiveAntiSpoof.get(context)
                    ?.score(bitmap, android.graphics.Rect(b.x, b.y, b.x + b.width, b.y + b.height))
                Selfie.Face(Bitmap.createBitmap(bitmap, l, t, r - l, btm - t), passive)
            }
        }
    }

    suspend fun submit(analysis: Analysis, borderRoute: String?, direction: String?, liveFace: Bitmap?,
                       expectedDocumentType: String? = null, openCase: Boolean = true,
                       liveness: com.pramaanai.officer.data.vision.LivenessReport? = null): Submission {
        if (!analysis.detectorAvailable) {
            return Submission.Failed(com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_detector_unavailable))
        }
        val prepared = withContext(Dispatchers.Default) { RegionCropper.prepare(analysis.bitmap, analysis.detections, analysis.text) }
        if (prepared.crops.isEmpty()) {
            return Submission.Failed(com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_no_regions))
        }
        val request = RegionVerificationRequest(
            documents = listOf(RegionDocument(listOf(analysis.bitmap.width, analysis.bitmap.height), prepared.crops,
                OnDeviceRegionDetector.NAME)),
            clientRequestId = java.util.UUID.randomUUID().toString(),
            liveFaceB64 = liveFace?.let { encodeFace(it) },
            borderRoute = borderRoute,
            direction = direction,
            deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID),
            capturedAt = Instant.now().toString(),
            expectedDocumentType = expectedDocumentType,
            deviceText = analysis.text.lines.take(400),
            openCase = openCase,
            liveness = if (liveFace != null) liveness else null,
        )
        request.clientRequestId?.let { CaptureStore.get(context).save(it, analysis.bitmap, liveFace) }
        val state = connectivity.check()
        if (state != ConnectivityState.ONLINE) {
            EncryptedDocVerifyQueue.get(context).enqueue(request, analysis.localChecks)
            DocVerifySyncWorker.enqueue(context)
            return Submission.Queued(analysis.localChecks,
                if (state == ConnectivityState.OFFLINE) com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_no_connection) else com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_server_unreachable))
        }
        return try {
            val outcome = RetrofitClient.docVerifyApi.verifyRegions(AuthSession.bearerHeader(), request)
            outcome.id?.let { CaptureStore.get(context).link(request.clientRequestId, it) }
            // The record's evidence (document image + live face crop) is kept
            // with the case for Review/History on any device and for the admin.
            background.launch { uploadEvidence(outcome) }
            Submission.Verified(outcome)
        } catch (e: retrofit2.HttpException) {
            if (e.code() == 503 || e.code() >= 500) {
                // Server busy or failing: keep the capture (same request id, so the
                // later sync is idempotent) instead of making the officer retake it.
                EncryptedDocVerifyQueue.get(context).enqueue(request, analysis.localChecks)
                DocVerifySyncWorker.enqueue(context)
                Submission.Queued(analysis.localChecks, com.pramaanai.officer.ui.i18n.L.s(
                    if (e.code() == 503) com.pramaanai.officer.R.string.rp_server_busy
                    else com.pramaanai.officer.R.string.rp_server_error))
            } else {
                Submission.Failed(if (e.code() == 422) com.pramaanai.officer.ui.i18n.L.f(com.pramaanai.officer.R.string.rp_regions_rejected, e.response()?.errorBody()?.string()?.take(200) ?: "")
                                  else com.pramaanai.officer.ui.i18n.L.f(com.pramaanai.officer.R.string.rp_request_rejected, e.code()))
            }
        } catch (e: Exception) {
            EncryptedDocVerifyQueue.get(context).enqueue(request, analysis.localChecks)
            DocVerifySyncWorker.enqueue(context)
            Submission.Queued(analysis.localChecks, com.pramaanai.officer.ui.i18n.L.s(com.pramaanai.officer.R.string.rp_connection_dropped))
        }
    }

    suspend fun recordAction(verificationId: String, action: String, reason: String?): Result<VerificationListItem> =
        runCatching { RetrofitClient.docVerifyApi.officerAction(AuthSession.bearerHeader(), verificationId, OfficerActionRequest(action, reason)) }

    suspend fun pendingCount(): Int = EncryptedDocVerifyQueue.get(context).count()

    /** The officer's own screenings, newest first (summary only — no personal fields). */
    suspend fun listMine(): Result<List<VerificationListItem>> =
        runCatching { RetrofitClient.docVerifyApi.listMine(AuthSession.bearerHeader()) }

    /** Attach the document image and live face crop to the verification's
     * case record as evidence — shown in Review/History on any device and to
     * the admin on the web console. (Verification itself only ever receives
     * region crops; this is the stored record of what was presented.) */
    suspend fun uploadEvidence(outcome: VerificationOutcome): Result<Int> = runCatching {
        val target = outcome.case?.screeningVerificationId ?: error("no case record to attach evidence to")
        val id = outcome.id ?: error("verification id missing")
        val (doc, face) = images(id)
        doc ?: error("the document image is not kept on this phone")
        fun part(name: String, bmp: Bitmap): okhttp3.MultipartBody.Part {
            val bytes = java.io.ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.JPEG, 88, it) }.toByteArray()
            return okhttp3.MultipartBody.Part.createFormData(name, "$name.jpg", bytes.toRequestBody("image/jpeg".toMediaTypeOrNull()))
        }
        withContext(Dispatchers.IO) {
            RetrofitClient.apiService.uploadImages(AuthSession.bearerHeader(), target, part("document_front", doc),
                null, face?.let { part("selfie", it) })
        }
        if (face != null) 2 else 1
    }

    /** Document image and live face crop for a verification: this phone's
     * encrypted copy if it has one, else the evidence stored with the case
     * (then cached here, encrypted). */
    suspend fun images(verificationId: String, screeningVerificationId: String? = null): Pair<Bitmap?, Bitmap?> {
        val store = CaptureStore.get(context)
        var doc = store.document(verificationId)
        var face = store.face(verificationId)
        if (doc == null && screeningVerificationId != null) {
            withContext(Dispatchers.IO) {
                val api = RetrofitClient.apiService
                doc = runCatching { api.downloadDocumentImage(AuthSession.bearerHeader(), screeningVerificationId).bytes() }
                    .getOrNull()?.let { android.graphics.BitmapFactory.decodeByteArray(it, 0, it.size) }
                if (face == null) face = runCatching { api.downloadSelfieImage(AuthSession.bearerHeader(), screeningVerificationId).bytes() }
                    .getOrNull()?.let { android.graphics.BitmapFactory.decodeByteArray(it, 0, it.size) }
            }
            doc?.let { store.save(verificationId, it, face) }
        }
        return doc to face
    }

    /** Full result + current case status and any reviewing officer's response. */
    suspend fun load(verificationId: String): Result<VerificationOutcome> =
        runCatching { RetrofitClient.docVerifyApi.get(AuthSession.bearerHeader(), verificationId).result }

    private fun downscale(src: Bitmap, maxSide: Int): Bitmap {
        val longest = max(src.width, src.height)
        if (longest <= maxSide) return src
        val s = maxSide.toFloat() / longest
        return Bitmap.createScaledBitmap(src, (src.width * s).toInt(), (src.height * s).toInt(), true)
    }

    private fun encodeFace(face: Bitmap): String {
        val out = java.io.ByteArrayOutputStream()
        downscale(face, 640).compress(Bitmap.CompressFormat.JPEG, 90, out)
        return android.util.Base64.encodeToString(out.toByteArray(), android.util.Base64.NO_WRAP)
    }
}
