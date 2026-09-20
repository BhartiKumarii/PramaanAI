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
import kotlin.math.sqrt

/**
 * MobileFaceNet-based face embedding via TFLite. Produces a 128-d
 * L2-normalized embedding from a 112x112 aligned face crop.
 *
 * The model file (mobilefacenet.tflite) should be placed in
 * `assets/models/`. If missing, [extract] returns null and the
 * pipeline falls back to the HOG-based FaceEmbedding — no crash,
 * no fake result.
 *
 * When the model IS present, this produces genuine neural embeddings
 * that are far more discriminative than HOG for face matching.
 * Cosine similarity ≥ 0.55 → same person; < 0.40 → different.
 */
object NeuralFaceEmbedding {
    private const val TAG = "NeuralFaceEmbedding"
    private const val MODEL_PATH = "models/mobilefacenet.tflite"
    private const val INPUT_SIZE = 112
    private const val EMBEDDING_DIM = 128

    private var interpreter: Interpreter? = null
    private var available = false
    private var initAttempted = false

    data class EmbeddingResult(
        val embedding: List<Float>?,
        val method: String,
        val available: Boolean,
    )

    fun init(context: Context) {
        if (initAttempted) return
        initAttempted = true
        try {
            val model = loadModel(context, MODEL_PATH)
            if (model != null) {
                val options = Interpreter.Options().apply {
                    numThreads = 2
                    useNNAPI = false
                }
                interpreter = Interpreter(model, options)
                available = true
                Log.i(TAG, "MobileFaceNet TFLite model loaded ($EMBEDDING_DIM-d embeddings)")
            } else {
                Log.w(TAG, "MobileFaceNet model not found at assets/$MODEL_PATH — neural embedding unavailable")
            }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to initialize MobileFaceNet: ${e.message}")
            interpreter = null
            available = false
        }
    }

    fun isAvailable(): Boolean = available

    /**
     * Extract a 128-d face embedding from a 112x112 aligned face bitmap.
     * Returns null if the model isn't loaded — caller should fall back to HOG.
     */
    fun extract(alignedFace: Bitmap): EmbeddingResult {
        val interp = interpreter
        if (interp == null || !available) {
            return EmbeddingResult(null, "NOT_AVAILABLE", false)
        }

        return try {
            val input = preprocessBitmap(alignedFace)
            val output = Array(1) { FloatArray(EMBEDDING_DIM) }
            interp.run(input, output)

            val raw = output[0]
            val embedding = l2Normalize(raw)

            EmbeddingResult(embedding.toList(), "mobilefacenet", true)
        } catch (e: Exception) {
            Log.e(TAG, "Inference failed", e)
            EmbeddingResult(null, "INFERENCE_ERROR", available)
        }
    }

    /**
     * Compute cosine similarity between two neural embeddings.
     * Only valid when both embeddings come from this module.
     */
    fun cosineSimilarity(a: List<Float>, b: List<Float>): Float {
        if (a.size != b.size) return 0f
        var dot = 0f
        var normA = 0f
        var normB = 0f
        for (i in a.indices) {
            dot += a[i] * b[i]
            normA += a[i] * a[i]
            normB += b[i] * b[i]
        }
        val denom = sqrt(normA) * sqrt(normB)
        return if (denom > 0f) dot / denom else 0f
    }

    /** Preprocess: resize to 112x112, normalize to [-1, 1], NHWC layout. */
    private fun preprocessBitmap(bitmap: Bitmap): ByteBuffer {
        val scaled = if (bitmap.width != INPUT_SIZE || bitmap.height != INPUT_SIZE) {
            Bitmap.createScaledBitmap(bitmap, INPUT_SIZE, INPUT_SIZE, true)
        } else bitmap

        val buffer = ByteBuffer.allocateDirect(1 * INPUT_SIZE * INPUT_SIZE * 3 * 4)
        buffer.order(ByteOrder.nativeOrder())

        val pixels = IntArray(INPUT_SIZE * INPUT_SIZE)
        scaled.getPixels(pixels, 0, INPUT_SIZE, 0, 0, INPUT_SIZE, INPUT_SIZE)

        for (pixel in pixels) {
            val r = Color.red(pixel)
            val g = Color.green(pixel)
            val b = Color.blue(pixel)
            buffer.putFloat((r - 127.5f) / 128.0f)
            buffer.putFloat((g - 127.5f) / 128.0f)
            buffer.putFloat((b - 127.5f) / 128.0f)
        }

        if (scaled !== bitmap) scaled.recycle()
        buffer.rewind()
        return buffer
    }

    private fun l2Normalize(vec: FloatArray): FloatArray {
        var sumSq = 0f
        for (v in vec) sumSq += v * v
        val norm = sqrt(sumSq)
        if (norm < 1e-10f) return vec
        return FloatArray(vec.size) { vec[it] / norm }
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
