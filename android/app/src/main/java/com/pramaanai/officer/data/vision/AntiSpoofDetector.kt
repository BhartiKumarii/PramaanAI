package com.pramaanai.officer.data.vision

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Color
import android.util.Log
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel

/**
 * Lightweight on-device anti-spoof detector via TFLite.
 *
 * Runs a binary classifier on a face crop: live vs. spoof (print/screen replay).
 * Model file: assets/models/antispoof.tflite
 *
 * When the model isn't available, falls back to the existing heuristic-based
 * LivenessDetector. The result explicitly states the method used so the
 * officer and the risk engine know what produced the score.
 */
object AntiSpoofDetector {
    private const val TAG = "AntiSpoofDetector"
    private const val MODEL_PATH = "models/antispoof.tflite"
    private const val INPUT_SIZE = 80

    private var interpreter: Interpreter? = null
    private var available = false
    private var initAttempted = false

    data class SpoofResult(
        val isLive: Boolean?,
        val spoofScore: Float,
        val method: String,
        val available: Boolean,
    )

    fun init(context: Context) {
        if (initAttempted) return
        initAttempted = true
        try {
            val model = loadModel(context, MODEL_PATH)
            if (model != null) {
                interpreter = Interpreter(model, Interpreter.Options().apply { numThreads = 2 })
                available = true
                Log.i(TAG, "Anti-spoof TFLite model loaded")
            } else {
                Log.w(TAG, "Anti-spoof model not found — using texture heuristic fallback")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to load anti-spoof model", e)
        }
    }

    fun isAvailable(): Boolean = available

    /**
     * Detect if a face crop is live or spoofed.
     * Returns null isLive when model isn't available — caller uses heuristic fallback.
     */
    fun detect(faceCrop: Bitmap): SpoofResult {
        val interp = interpreter
        if (interp == null || !available) {
            return heuristicFallback(faceCrop)
        }

        return try {
            val input = preprocessBitmap(faceCrop)
            val output = Array(1) { FloatArray(2) }
            interp.run(input, output)

            val liveProb = output[0][0]
            val spoofProb = output[0][1]
            val isLive = liveProb > spoofProb

            SpoofResult(
                isLive = isLive,
                spoofScore = spoofProb.coerceIn(0f, 1f),
                method = "tflite_antispoof",
                available = true,
            )
        } catch (e: Exception) {
            Log.e(TAG, "Anti-spoof inference failed", e)
            heuristicFallback(faceCrop)
        }
    }

    /**
     * Texture-based heuristic fallback: analyzes frequency content and
     * color uniformity to detect print/screen artifacts. Not as accurate
     * as the neural model but better than no check at all.
     */
    private fun heuristicFallback(bitmap: Bitmap): SpoofResult {
        val w = bitmap.width
        val h = bitmap.height
        if (w < 20 || h < 20) {
            return SpoofResult(null, 0.5f, "too_small", false)
        }

        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)

        // Laplacian variance as sharpness proxy
        var lapSum = 0.0
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val center = luma(pixels[y * w + x])
                val lap = kotlin.math.abs(
                    4.0 * center -
                        luma(pixels[(y - 1) * w + x]) -
                        luma(pixels[(y + 1) * w + x]) -
                        luma(pixels[y * w + (x - 1)]) -
                        luma(pixels[y * w + (x + 1)])
                )
                lapSum += lap * lap
            }
        }
        val lapVar = lapSum / ((w - 2) * (h - 2))

        // Color channel uniformity (screens/prints have narrower distributions)
        var rSum = 0.0; var gSum = 0.0; var bSum = 0.0
        var rSqSum = 0.0; var gSqSum = 0.0; var bSqSum = 0.0
        for (p in pixels) {
            val r = Color.red(p).toDouble()
            val g = Color.green(p).toDouble()
            val b = Color.blue(p).toDouble()
            rSum += r; gSum += g; bSum += b
            rSqSum += r * r; gSqSum += g * g; bSqSum += b * b
        }
        val n = pixels.size.toDouble()
        val rVar = (rSqSum / n) - (rSum / n) * (rSum / n)
        val gVar = (gSqSum / n) - (gSum / n) * (gSum / n)
        val bVar = (bSqSum / n) - (bSum / n) * (bSum / n)
        val avgColorVar = (rVar + gVar + bVar) / 3.0

        // High Laplacian variance + high color variance = likely real
        // Low both = flat/blurry, possibly screen/print
        val sharpnessScore = (lapVar / 2000.0).coerceIn(0.0, 1.0)
        val colorScore = (avgColorVar / 2000.0).coerceIn(0.0, 1.0)
        val combined = (0.6 * sharpnessScore + 0.4 * colorScore).coerceIn(0.0, 1.0)
        val spoofScore = (1.0 - combined).toFloat()

        return SpoofResult(
            isLive = if (combined > 0.5) true else null,
            spoofScore = spoofScore,
            method = "texture_heuristic",
            available = false,
        )
    }

    private fun luma(pixel: Int): Double =
        0.299 * Color.red(pixel) + 0.587 * Color.green(pixel) + 0.114 * Color.blue(pixel)

    private fun preprocessBitmap(bitmap: Bitmap): ByteBuffer {
        val scaled = Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)
        val buffer = ByteBuffer.allocateDirect(1 * INPUT_SIZE * INPUT_SIZE * 3 * 4)
        buffer.order(ByteOrder.nativeOrder())

        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        scaled.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)

        for (pixel in pixels) {
            buffer.putFloat(Color.red(pixel) / 255.0f)
            buffer.putFloat(Color.green(pixel) / 255.0f)
            buffer.putFloat(Color.blue(pixel) / 255.0f)
        }

        if (scaled !== bitmap) scaled.recycle()
        buffer.rewind()
        return buffer
    }

    private fun loadModel(context: Context, path: String): MappedByteBuffer? {
        return try {
            val fd = context.assets.openFd(path)
            val stream = FileInputStream(fd.fileDescriptor)
            val channel = stream.channel
            val model = channel.map(FileChannel.MapMode.READ_ONLY, fd.startOffset, fd.declaredLength)
            stream.close()
            model
        } catch (_: Exception) {
            null
        }
    }
}
