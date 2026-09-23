package com.pramaanai.officer.data.docverify

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.RectF
import java.io.Closeable
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min

/** YOLO11n region detector running on the phone (ONNX Runtime).
 *
 * Trained on this project's labelled real document photos + synthetic
 * documents (scripts/docverify/yolo). It only LOCATES regions — document,
 * photograph, MRZ, QR, barcode, stamp, yellow/gold visual feature. It never
 * decides whether anything is genuine; the located regions are cropped and
 * sent to the server for OCR, validation and forensics. */
class OnDeviceRegionDetector private constructor(
    private val env: OrtEnvironment,
    private val session: OrtSession,
) : Closeable {

    data class Detection(val label: String, val box: RectF, val score: Float)

    fun detect(bitmap: Bitmap, confThreshold: Float = 0.35f, iouThreshold: Float = 0.5f): List<Detection> {
        val (input, scale, padX, padY) = letterbox(bitmap)
        val tensor = OnnxTensor.createTensor(env, input, longArrayOf(1, 3, INPUT.toLong(), INPUT.toLong()))
        val raw = tensor.use { t ->
            session.run(mapOf(session.inputNames.first() to t)).use { result ->
                @Suppress("UNCHECKED_CAST")
                (result[0].value as Array<Array<FloatArray>>)[0] // [4 + classes][anchors]
            }
        }
        val anchors = raw[0].size
        val candidates = ArrayList<Detection>()
        for (a in 0 until anchors) {
            var best = -1
            var bestScore = 0f
            for (c in CLASSES.indices) {
                val s = raw[4 + c][a]
                if (s > bestScore) { bestScore = s; best = c }
            }
            if (best < 0 || bestScore < confThreshold) continue
            val cx = raw[0][a]; val cy = raw[1][a]; val w = raw[2][a]; val h = raw[3][a]
            val box = RectF(
                ((cx - w / 2 - padX) / scale).coerceIn(0f, bitmap.width.toFloat()),
                ((cy - h / 2 - padY) / scale).coerceIn(0f, bitmap.height.toFloat()),
                ((cx + w / 2 - padX) / scale).coerceIn(0f, bitmap.width.toFloat()),
                ((cy + h / 2 - padY) / scale).coerceIn(0f, bitmap.height.toFloat()),
            )
            candidates.add(Detection(CLASSES[best], box, bestScore))
        }
        return nms(candidates, iouThreshold)
    }

    private data class Letterboxed(val data: FloatBuffer, val scale: Float, val padX: Float, val padY: Float)

    private fun letterbox(src: Bitmap): Letterboxed {
        val scale = min(INPUT.toFloat() / src.width, INPUT.toFloat() / src.height)
        val nw = (src.width * scale).toInt()
        val nh = (src.height * scale).toInt()
        val padX = (INPUT - nw) / 2f
        val padY = (INPUT - nh) / 2f
        val canvasBitmap = Bitmap.createBitmap(INPUT, INPUT, Bitmap.Config.ARGB_8888)
        Canvas(canvasBitmap).apply {
            drawColor(Color.rgb(114, 114, 114))
            drawBitmap(Bitmap.createScaledBitmap(src, nw, nh, true), padX, padY, Paint(Paint.FILTER_BITMAP_FLAG))
        }
        val pixels = IntArray(INPUT * INPUT)
        canvasBitmap.getPixels(pixels, 0, INPUT, 0, 0, INPUT, INPUT)
        val buffer = FloatBuffer.allocate(3 * INPUT * INPUT)
        val plane = INPUT * INPUT
        for (i in pixels.indices) {
            val p = pixels[i]
            buffer.put(i, ((p shr 16) and 0xFF) / 255f)
            buffer.put(plane + i, ((p shr 8) and 0xFF) / 255f)
            buffer.put(2 * plane + i, (p and 0xFF) / 255f)
        }
        return Letterboxed(buffer, scale, padX, padY)
    }

    private fun nms(dets: List<Detection>, iouThreshold: Float): List<Detection> {
        val kept = ArrayList<Detection>()
        for (label in dets.map { it.label }.distinct()) {
            val sorted = dets.filter { it.label == label }.sortedByDescending { it.score }.toMutableList()
            while (sorted.isNotEmpty()) {
                val top = sorted.removeAt(0)
                kept.add(top)
                sorted.removeAll { iou(it.box, top.box) > iouThreshold }
            }
        }
        return kept
    }

    private fun iou(a: RectF, b: RectF): Float {
        val ix = max(0f, min(a.right, b.right) - max(a.left, b.left))
        val iy = max(0f, min(a.bottom, b.bottom) - max(a.top, b.top))
        val inter = ix * iy
        val union = a.width() * a.height() + b.width() * b.height() - inter
        return if (union > 0) inter / union else 0f
    }

    override fun close() {
        session.close()
    }

    companion object {
        const val MODEL_ASSET = "pramaan_regions_yolo11n.onnx"
        const val NAME = "yolo11n-onnx (on-device)"
        private const val INPUT = 640
        val CLASSES = listOf("document", "photograph", "mrz", "qr_code", "barcode", "stamp", "yellow_gold_feature")

        @Volatile private var instance: OnDeviceRegionDetector? = null

        /** Null if the model asset is missing or ONNX Runtime can't load it —
         * the caller then reports that regions could not be located, instead
         * of silently uploading the whole image. */
        fun get(context: Context): OnDeviceRegionDetector? = instance ?: synchronized(this) {
            instance ?: runCatching {
                val env = OrtEnvironment.getEnvironment()
                val bytes = context.assets.open(MODEL_ASSET).use { it.readBytes() }
                OnDeviceRegionDetector(env, env.createSession(bytes, OrtSession.SessionOptions()))
            }.getOrNull()?.also { instance = it }
        }
    }
}
