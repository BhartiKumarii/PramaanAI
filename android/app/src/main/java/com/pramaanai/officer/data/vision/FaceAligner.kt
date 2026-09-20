package com.pramaanai.officer.data.vision

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.RectF
import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.face.FaceDetection
import com.google.mlkit.vision.face.FaceDetectorOptions
import com.google.mlkit.vision.face.FaceLandmark
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.math.atan2

/**
 * Face alignment using ML Kit's face detection with landmark mode.
 * Detects faces with eye/nose landmarks, computes the rotation angle
 * from the eye line, and produces a 112x112 aligned, upright face crop
 * suitable for embedding extraction.
 *
 * This significantly improves face embedding quality by normalizing
 * head pose before feature extraction.
 */
object FaceAligner {
    private const val TAG = "FaceAligner"
    private const val ALIGNED_SIZE = 112

    private val detector by lazy {
        FaceDetection.getClient(
            FaceDetectorOptions.Builder()
                .setPerformanceMode(FaceDetectorOptions.PERFORMANCE_MODE_ACCURATE)
                .setLandmarkMode(FaceDetectorOptions.LANDMARK_MODE_ALL)
                .setMinFaceSize(0.15f)
                .build(),
        )
    }

    fun init(context: Context) {
        Log.i(TAG, "FaceAligner initialized (ML Kit landmark-based alignment)")
    }

    data class AlignmentResult(
        val alignedFace: Bitmap?,
        val faceRect: RectF?,
        val rotationDegrees: Float,
        val confidence: Float,
        val method: String,
    )

    suspend fun alignFace(bitmap: Bitmap): AlignmentResult {
        return try {
            alignWithMLKit(bitmap)
        } catch (e: Exception) {
            Log.w(TAG, "Face alignment failed", e)
            AlignmentResult(null, null, 0f, 0f, "error")
        }
    }

    private suspend fun alignWithMLKit(bitmap: Bitmap): AlignmentResult {
        val image = InputImage.fromBitmap(bitmap, 0)
        val faces = suspendCancellableCoroutine { cont ->
            detector.process(image)
                .addOnSuccessListener { result -> cont.resume(result) }
                .addOnFailureListener { e -> cont.resumeWithException(e) }
        }

        if (faces.isEmpty()) {
            return AlignmentResult(null, null, 0f, 0f, "no_face")
        }

        val face = faces[0]
        val bbox = face.boundingBox
        val faceRect = RectF(
            bbox.left.toFloat(), bbox.top.toFloat(),
            bbox.right.toFloat(), bbox.bottom.toFloat(),
        )

        // Compute rotation from eye landmarks
        var angle = 0f
        val leftEye = face.getLandmark(FaceLandmark.LEFT_EYE)
        val rightEye = face.getLandmark(FaceLandmark.RIGHT_EYE)

        if (leftEye != null && rightEye != null) {
            val eyeDx = rightEye.position.x - leftEye.position.x
            val eyeDy = rightEye.position.y - leftEye.position.y
            angle = Math.toDegrees(atan2(eyeDy.toDouble(), eyeDx.toDouble())).toFloat()
        }

        val aligned = cropAndAlign(bitmap, faceRect, angle)

        return AlignmentResult(
            alignedFace = aligned,
            faceRect = faceRect,
            rotationDegrees = angle,
            confidence = 1.0f,
            method = "mlkit_landmarks",
        )
    }

    private fun cropAndAlign(bitmap: Bitmap, faceRect: RectF, angleDeg: Float): Bitmap? {
        val cx = faceRect.centerX()
        val cy = faceRect.centerY()
        val halfSize = maxOf(faceRect.width(), faceRect.height()) * 0.7f

        val cropLeft = (cx - halfSize).coerceAtLeast(0f)
        val cropTop = (cy - halfSize).coerceAtLeast(0f)
        val cropRight = (cx + halfSize).coerceAtMost(bitmap.width.toFloat())
        val cropBottom = (cy + halfSize).coerceAtMost(bitmap.height.toFloat())
        val cropW = (cropRight - cropLeft).toInt()
        val cropH = (cropBottom - cropTop).toInt()

        if (cropW < 20 || cropH < 20) return null

        val cropped = Bitmap.createBitmap(bitmap, cropLeft.toInt(), cropTop.toInt(), cropW, cropH)

        val matrix = Matrix()
        if (kotlin.math.abs(angleDeg) > 0.5f) {
            matrix.postRotate(-angleDeg, cropW / 2f, cropH / 2f)
        }
        matrix.postScale(
            ALIGNED_SIZE.toFloat() / cropW,
            ALIGNED_SIZE.toFloat() / cropH,
        )

        val aligned = Bitmap.createBitmap(ALIGNED_SIZE, ALIGNED_SIZE, Bitmap.Config.ARGB_8888)
        val canvas = Canvas(aligned)
        canvas.drawBitmap(cropped, matrix, null)
        if (cropped !== bitmap) cropped.recycle()

        return aligned
    }
}
