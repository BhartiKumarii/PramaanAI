package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import android.graphics.Color
import kotlin.math.atan2
import kotlin.math.hypot
import kotlin.math.min

/**
 * Faithful Kotlin port of the backend's classical HOG-style face
 * embedding (see app/services/face/embedding.py — that module's own
 * docstring: "every device implementation must match"). No face
 * detection/cropping happens here, matching the backend's
 * ClassicalFaceProvider: both the document photo and the live selfie
 * are treated as already face-framed images, so the whole captured
 * bitmap is embedded directly. Deterministic, no ML model, no network
 * call — genuinely computed from the pixels, not a placeholder.
 *
 * Output is a 1296-length Float vector (12x12 cells x 9 orientation
 * bins), sent to the server as document_face_embedding /
 * live_face_embedding for a real server-side cosine-similarity
 * comparison — this module never computes the match itself.
 */
object FaceEmbedding {
    private const val EMBED_SIZE = 96
    private const val CELL_SIZE = 8
    private const val N_BINS = 9
    private const val N_CELLS = EMBED_SIZE / CELL_SIZE // 12

    // Same 3x3 kernels as the backend (no kernel flip — this is
    // cross-correlation, matching the Python reference's _convolve2d
    // exactly, not a "true" flipped convolution).
    private val SOBEL_X = arrayOf(
        floatArrayOf(-1f, 0f, 1f),
        floatArrayOf(-2f, 0f, 2f),
        floatArrayOf(-1f, 0f, 1f),
    )
    private val SOBEL_Y = arrayOf(
        floatArrayOf(-1f, -2f, -1f),
        floatArrayOf(0f, 0f, 0f),
        floatArrayOf(1f, 2f, 1f),
    )

    fun extractEmbedding(bitmap: Bitmap): List<Float> {
        val gray96 = grayscaleAndResize(bitmap)
        val gx = convolve2d(gray96, SOBEL_X)
        val gy = convolve2d(gray96, SOBEL_Y)

        val magnitude = Array(EMBED_SIZE) { y -> FloatArray(EMBED_SIZE) { x -> hypot(gx[y][x], gy[y][x]) } }
        val angle = Array(EMBED_SIZE) { y ->
            FloatArray(EMBED_SIZE) { x ->
                var deg = Math.toDegrees(atan2(gy[y][x].toDouble(), gx[y][x].toDouble())).toFloat()
                deg %= 180f
                if (deg < 0f) deg += 180f
                deg
            }
        }

        val binWidth = 180f / N_BINS
        val histogram = ArrayList<Float>(N_CELLS * N_CELLS * N_BINS)
        for (cy in 0 until N_CELLS) {
            for (cx in 0 until N_CELLS) {
                val y0 = cy * CELL_SIZE
                val x0 = cx * CELL_SIZE
                val bins = FloatArray(N_BINS)
                for (dy in 0 until CELL_SIZE) {
                    for (dx in 0 until CELL_SIZE) {
                        val mag = magnitude[y0 + dy][x0 + dx]
                        val ang = angle[y0 + dy][x0 + dx]
                        val binIndex = min((ang / binWidth).toInt(), N_BINS - 1)
                        bins[binIndex] += mag
                    }
                }
                var normSq = 0f
                for (v in bins) normSq += v * v
                val norm = if (normSq > 0f) kotlin.math.sqrt(normSq) else 1f
                for (v in bins) histogram.add(v / norm)
            }
        }
        return histogram
    }

    /** PIL's `.convert("L")` weights (ITU-R 601-2), then a bilinear
     * resize to 96x96 — same order as the backend (grayscale, then
     * resize), using the platform's built-in bilinear filter so results
     * track PIL.Image.BILINEAR closely without hand-rolling the filter. */
    private fun grayscaleAndResize(bitmap: Bitmap): Array<FloatArray> {
        val w = bitmap.width
        val h = bitmap.height
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)
        val grayBitmap = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val grayPixels = IntArray(w * h)
        for (i in pixels.indices) {
            val p = pixels[i]
            val gray = (0.299f * Color.red(p) + 0.587f * Color.green(p) + 0.114f * Color.blue(p))
                .toInt().coerceIn(0, 255)
            grayPixels[i] = Color.argb(255, gray, gray, gray)
        }
        grayBitmap.setPixels(grayPixels, 0, w, 0, 0, w, h)

        val scaled = Bitmap.createScaledBitmap(grayBitmap, EMBED_SIZE, EMBED_SIZE, true)
        val out = Array(EMBED_SIZE) { FloatArray(EMBED_SIZE) }
        val scaledPixels = IntArray(EMBED_SIZE * EMBED_SIZE)
        scaled.getPixels(scaledPixels, 0, EMBED_SIZE, 0, 0, EMBED_SIZE, EMBED_SIZE)
        for (y in 0 until EMBED_SIZE) {
            for (x in 0 until EMBED_SIZE) {
                out[y][x] = Color.red(scaledPixels[y * EMBED_SIZE + x]).toFloat()
            }
        }
        if (grayBitmap !== scaled) grayBitmap.recycle()
        scaled.recycle()
        return out
    }

    /** Edge-padded (replicate border) 3x3 cross-correlation — matches
     * `np.pad(..., mode="edge")` + the backend's unflipped kernel sweep. */
    private fun convolve2d(image: Array<FloatArray>, kernel: Array<FloatArray>): Array<FloatArray> {
        val size = image.size
        fun at(y: Int, x: Int): Float {
            val cy = y.coerceIn(0, size - 1)
            val cx = x.coerceIn(0, size - 1)
            return image[cy][cx]
        }
        val out = Array(size) { FloatArray(size) }
        for (y in 0 until size) {
            for (x in 0 until size) {
                var sum = 0f
                for (i in 0 until 3) {
                    for (j in 0 until 3) {
                        sum += kernel[i][j] * at(y + i - 1, x + j - 1)
                    }
                }
                out[y][x] = sum
            }
        }
        return out
    }
}
