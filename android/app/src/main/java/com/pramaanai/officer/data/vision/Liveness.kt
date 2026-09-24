package com.pramaanai.officer.data.vision

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Rect
import com.google.mlkit.vision.face.Face
import java.nio.FloatBuffer
import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.min

/**
 * Liveness of the traveller's live photo — evidence for the officer, never a
 * verdict.
 *
 * Active: two prompts in random order (blink, turn the head to one side and
 * back), checked frame by frame with ML Kit face landmarks/classification. The
 * same tracked face must complete both; if a different face appears the
 * prompts restart. A printed photo or a still on a screen cannot blink.
 *
 * Passive: MiniFASNet-V2 (minivision Silent-Face-Anti-Spoofing, Apache-2.0,
 * 1.7 MB ONNX) on the captured frame — probability that the face is a real
 * person rather than a print or a screen replay.
 */
enum class LivenessChallenge { BLINK, TURN_HEAD }

data class LivenessReport(
    val active: String,                 // PASSED | NOT_COMPLETED | NOT_PERFORMED
    val challenges: List<String>,
    val passiveScore: Float?,
    val passiveModel: String?,
    val source: String,                 // camera | gallery
    val durationMs: Long?,
)

class ActiveLivenessTracker(val challenges: List<LivenessChallenge> = LivenessChallenge.values().toList().shuffled()) {

    enum class Hint { NO_FACE, MULTIPLE_FACES, FOLLOW_PROMPT, PASSED }

    var index = 0; private set
    var passed = false; private set
    private var trackingId: Int? = null
    private var startedAt = 0L
    var passedAt = 0L; private set

    // Per-prompt progress.
    private var sawOpen = false
    private var sawClosed = false
    private var sawCentre = false
    private var sawTurned = false

    val current: LivenessChallenge? get() = challenges.getOrNull(index)

    fun reset() {
        index = 0; passed = false; trackingId = null; startedAt = 0L; passedAt = 0L; resetPrompt()
    }

    private fun resetPrompt() { sawOpen = false; sawClosed = false; sawCentre = false; sawTurned = false }

    fun onFaces(faces: List<Face>, now: Long = System.currentTimeMillis()): Hint {
        if (faces.isEmpty()) return if (passed) Hint.PASSED else Hint.NO_FACE
        if (faces.size > 1) return Hint.MULTIPLE_FACES
        val f = faces[0]
        val id = f.trackingId
        if (trackingId != null && id != null && id != trackingId) {
            // A different face took the place of the one that did the prompts.
            reset()
        }
        if (trackingId == null) { trackingId = id; startedAt = now }
        if (passed) return Hint.PASSED
        when (current) {
            LivenessChallenge.BLINK -> {
                val l = f.leftEyeOpenProbability
                val r = f.rightEyeOpenProbability
                if (l != null && r != null) {
                    if (!sawOpen && l > 0.7f && r > 0.7f) sawOpen = true
                    else if (sawOpen && !sawClosed && l < 0.25f && r < 0.25f) sawClosed = true
                    else if (sawClosed && l > 0.6f && r > 0.6f) advance(now)
                }
            }
            LivenessChallenge.TURN_HEAD -> {
                val y = abs(f.headEulerAngleY)
                if (!sawCentre && y < 10f) sawCentre = true
                else if (sawCentre && !sawTurned && y > 22f) sawTurned = true
                else if (sawTurned && y < 12f) advance(now)
            }
            null -> Unit
        }
        return if (passed) Hint.PASSED else Hint.FOLLOW_PROMPT
    }

    private fun advance(now: Long) {
        resetPrompt()
        index++
        if (index >= challenges.size) { passed = true; passedAt = now }
    }

    fun durationMs(): Long? = if (passed && startedAt > 0) passedAt - startedAt else null

    fun report(passiveScore: Float?): LivenessReport = LivenessReport(
        active = if (passed) "PASSED" else "NOT_COMPLETED",
        challenges = challenges.map { it.name },
        passiveScore = passiveScore,
        passiveModel = if (passiveScore != null) PassiveAntiSpoof.NAME else null,
        source = "camera",
        durationMs = durationMs(),
    )
}

/** MiniFASNet-V2 on-device. Null when the model can't be loaded. */
class PassiveAntiSpoof private constructor(private val env: OrtEnvironment, private val session: OrtSession) {

    /** Probability (0..1) that [face] in [bitmap] is a real person. The crop
     * follows the upstream "2.7_80x80" recipe: 2.7x the face box, clamped
     * inside the image, resized to 80x80, BGR, raw 0..255 values. */
    fun score(bitmap: Bitmap, face: Rect): Float? = runCatching {
        val crop = crop27(bitmap, face)
        val px = IntArray(SIZE * SIZE)
        crop.getPixels(px, 0, SIZE, 0, 0, SIZE, SIZE)
        val buf = FloatBuffer.allocate(3 * SIZE * SIZE)
        val plane = SIZE * SIZE
        for (i in 0 until plane) {
            val c = px[i]
            buf.put(i, (c and 0xFF).toFloat())                 // B
            buf.put(plane + i, ((c shr 8) and 0xFF).toFloat()) // G
            buf.put(2 * plane + i, ((c shr 16) and 0xFF).toFloat()) // R
        }
        OnnxTensor.createTensor(env, buf, longArrayOf(1, 3, SIZE.toLong(), SIZE.toLong())).use { t ->
            session.run(mapOf(session.inputNames.first() to t)).use { out ->
                @Suppress("UNCHECKED_CAST")
                val logits = (out[0].value as Array<FloatArray>)[0]
                val m = logits.max()
                val e = logits.map { exp((it - m).toDouble()) }
                (e[REAL_CLASS] / e.sum()).toFloat()
            }
        }
    }.getOrNull()

    private fun crop27(bitmap: Bitmap, box: Rect): Bitmap {
        val w = bitmap.width; val h = bitmap.height
        val bw = box.width().toFloat().coerceAtLeast(1f); val bh = box.height().toFloat().coerceAtLeast(1f)
        val scale = min(min((h - 1) / bh, (w - 1) / bw), SCALE)
        val nw = bw * scale; val nh = bh * scale
        val cx = box.exactCenterX(); val cy = box.exactCenterY()
        var l = cx - nw / 2; var t = cy - nh / 2; var r = cx + nw / 2; var b = cy + nh / 2
        if (l < 0) { r -= l; l = 0f }
        if (t < 0) { b -= t; t = 0f }
        if (r > w - 1) { l -= r - w + 1; r = (w - 1).toFloat() }
        if (b > h - 1) { t -= b - h + 1; b = (h - 1).toFloat() }
        val x0 = l.toInt().coerceIn(0, w - 1); val y0 = t.toInt().coerceIn(0, h - 1)
        val cw = (r.toInt() - x0 + 1).coerceIn(1, w - x0); val ch = (b.toInt() - y0 + 1).coerceIn(1, h - y0)
        return Bitmap.createScaledBitmap(Bitmap.createBitmap(bitmap, x0, y0, cw, ch), SIZE, SIZE, true)
    }

    companion object {
        const val MODEL_ASSET = "minifasnet_v2.onnx"
        const val NAME = "MiniFASNet-V2 2.7_80x80 (on-device)"
        private const val SIZE = 80
        private const val SCALE = 2.7f
        private const val REAL_CLASS = 1  // upstream labels: 1 = real face; 0 / 2 = spoof

        @Volatile private var instance: PassiveAntiSpoof? = null

        fun get(context: Context): PassiveAntiSpoof? = instance ?: synchronized(this) {
            instance ?: runCatching {
                val env = OrtEnvironment.getEnvironment()
                val bytes = context.assets.open(MODEL_ASSET).use { it.readBytes() }
                PassiveAntiSpoof(env, env.createSession(bytes, OrtSession.SessionOptions()))
            }.getOrNull()?.also { instance = it }
        }
    }
}
