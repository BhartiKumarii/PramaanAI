package com.pramaanai.officer.data.vision

import android.graphics.Bitmap
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.pramaanai.officer.data.model.DetectedFace
import com.pramaanai.officer.data.model.FaceDetectionResult
import com.pramaanai.officer.data.model.LocationBox
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** On-device face detection (presence/count/position) — a real Google
 * Play Services detector, same on-device/no-network posture as
 * DocumentOcrExtractor's text recognizer. Only the structured
 * FaceDetectionResult (status/count/bounding boxes) crosses the wire,
 * never the selfie image itself — mirrors the backend's
 * app/services/face/base.py FaceDetectionResult field-for-field so Gson's
 * snake_case mapping lines up without extra glue. Distinct from
 * FaceEmbedding's match/no-match comparison: this only answers "is
 * there a face here, and how many", which is what a fraud check like
 * "multiple faces in the live capture" actually needs. */
object FaceDetectionAnalyzer {

    private val detector by lazy {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
                .build(),
        )
    }

    suspend fun detect(bitmap: Bitmap): FaceDetectionResult {
        val image = InputImage.fromBitmap(bitmap, 0)
        val faces = suspendCancellableCoroutine { cont ->
            detector.process(image)
                .addOnSuccessListener { result -> cont.resume(result) }
                .addOnFailureListener { e -> cont.resumeWithException(e) }
        }

        val width = bitmap.width
        val height = bitmap.height
        val detected = faces.map { face ->
            val box = face.boundingBox
            val x0 = box.left.coerceAtLeast(0)
            val y0 = box.top.coerceAtLeast(0)
            val x1 = box.right.coerceAtMost(width)
            val y1 = box.bottom.coerceAtMost(height)
            val touchesEdge = x0 <= 1 || y0 <= 1 || x1 >= width - 1 || y1 >= height - 1
            DetectedFace(
                location = LocationBox(x0 = x0, y0 = y0, x1 = x1, y1 = y1),
                // ML Kit's default detector doesn't expose a single face
                // "confidence" score the way a raw model does — 1.0 for
                // every face it actually returns (it only returns faces
                // that pass its own internal threshold), documented as
                // such rather than implying a graded score that doesn't
                // exist here.
                confidence = 1.0,
                touchesEdge = touchesEdge,
            )
        }

        return when {
            detected.isEmpty() -> FaceDetectionResult(
                status = "NO_FACE", faces = emptyList(), reason = "no face detected in the image",
            )
            detected.size > 1 -> FaceDetectionResult(
                status = "MULTIPLE_FACES", faces = detected,
                reason = "${detected.size} faces detected in the image (expected exactly one)",
            )
            else -> {
                val face = detected[0]
                val edgeNote = if (face.touchesEdge) {
                    " — the detected face touches the image edge, possibly cropped/obscured"
                } else ""
                FaceDetectionResult(
                    status = "SINGLE_FACE", faces = detected,
                    reason = "1 face detected$edgeNote",
                )
            }
        }
    }
}
