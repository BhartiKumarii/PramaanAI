package com.pramaanai.officer.ui.capture

import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.workflow.ExtractedFieldRow
import com.pramaanai.officer.ui.workflow.PhotoTile
import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.data.sync.PendingSubmissionWorker
import com.pramaanai.officer.data.vision.AntiSpoofDetector
import com.pramaanai.officer.data.vision.DeepfakeAnalyzer
import com.pramaanai.officer.data.vision.DocumentBarcodeScanner
import com.pramaanai.officer.data.vision.DocumentOcrExtractor
import com.pramaanai.officer.data.vision.FaceAligner
import com.pramaanai.officer.data.vision.FaceDetectionAnalyzer
import com.pramaanai.officer.data.vision.FaceEmbedding
import com.pramaanai.officer.data.vision.ImageQualityGate
import com.pramaanai.officer.data.vision.NeuralFaceEmbedding
import com.pramaanai.officer.data.vision.OpenCVManager
import com.pramaanai.officer.data.vision.TamperingAnalyzer
import com.pramaanai.officer.ui.components.ConfidenceTag
import com.pramaanai.officer.ui.components.GridPatternBackground
import com.pramaanai.officer.ui.components.WorkflowStepper
import androidx.compose.ui.text.font.FontFamily
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import kotlin.random.Random

// Helper functions defined BEFORE the main CaptureScreen function
@Composable
fun QualityIndicatorsRow(metrics: OpenCVManager.QualityMetrics) {
    val indicators = listOf(
        QualityIndicator(stringResource(R.string.quality_blur), metrics.blurScore, 0.7f),
        QualityIndicator(stringResource(R.string.quality_glare), 1f - metrics.glareScore, 0.7f),
        QualityIndicator(stringResource(R.string.quality_lighting), metrics.lightingScore, 0.6f),
        QualityIndicator(stringResource(R.string.quality_shadows), 1f - metrics.shadowScore, 0.6f),
    )
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        indicators.forEach { indicator ->
            QualityIndicatorBox(indicator)
        }
    }
}

@Composable
fun QualityIndicatorBox(indicator: QualityIndicator) {
    val isGood = indicator.score >= indicator.threshold
    Card(
        modifier = Modifier.size(60.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isGood) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.errorContainer,
        ),
    ) {
        Column(
            modifier = Modifier.fillMaxSize().padding(8.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(Modifier.height(4.dp))
            Text(
                text = "${(indicator.score * 100).toInt()}%",
                style = MaterialTheme.typography.labelSmall,
                color = if (isGood) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onErrorContainer,
            )
            Text(
                text = indicator.label,
                style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                color = if (isGood) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onErrorContainer,
            )
        }
    }
}

data class QualityIndicator(
    val label: String,
    val score: Float,
    val threshold: Float,
)

@Composable
fun EnhancedCameraPreview(
    modifier: Modifier = Modifier,
    lensFacing: Int,
    onImageCaptureReady: (ImageCapture) -> Unit,
    onAnalysisReady: (ImageAnalysis) -> Unit,
    step: CaptureStep,
    previewState: MutableState<DocumentPreviewState>,
    scanLineProgress: Float,
    onAutoCapture: (Bitmap) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    AndroidView(
        modifier = modifier
            .drawBehind { drawDocumentOverlay(previewState.value, scanLineProgress) }
            .clip(RoundedCornerShape(12.dp)),
        factory = { ctx ->
            PreviewView(ctx).apply {
                // COMPATIBLE (TextureView-backed), not the PERFORMANCE default
                // (SurfaceView-backed) — a SurfaceView renders on its own
                // hardware compositing layer outside normal Compose z-order,
                // which was pushing the capture/upload buttons and document
                // overlay out of their real on-screen position around the
                // preview. TextureView composites like any other View.
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            }
        },
        update = { previewView ->
            val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().also {
                    it.surfaceProvider = previewView.surfaceProvider
                }
                val capture = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                    .build()
                val analysisExecutor = java.util.concurrent.Executors.newSingleThreadExecutor()
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setTargetResolution(android.util.Size(640, 480))
                    .build()
                    .also { imgAnalysis ->
                        imgAnalysis.setAnalyzer(analysisExecutor) { imageProxy ->
                            val newState = analyzeFrame(imageProxy, step, onAutoCapture)
                            if (newState != null) {
                                Handler(Looper.getMainLooper()).post { previewState.value = newState }
                            }
                        }
                        onAnalysisReady(imgAnalysis)
                    }
                val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview, capture, analysis)
                    onImageCaptureReady(capture)
                } catch (e: Exception) {
                    Log.e("CameraPreview", "Camera bind failed", e)
                }
            }, ContextCompat.getMainExecutor(context))
        },
    )
}

fun analyzeFrame(
    imageProxy: ImageProxy,
    step: CaptureStep,
    onAutoCapture: (Bitmap) -> Unit,
): DocumentPreviewState? {
    if (step != CaptureStep.DOCUMENT_FRONT && step != CaptureStep.DOCUMENT_BACK) {
        imageProxy.close()
        return null
    }

    val mediaImage = imageProxy.image ?: run { imageProxy.close(); return null }
    val rotation = imageProxy.imageInfo.rotationDegrees
    Log.d("FrameAnalysis", "Frame: ${mediaImage.width}x${mediaImage.height}, format=${mediaImage.format}, rotation=$rotation")
    val bitmap = mediaImageToBitmap(mediaImage, rotation)
    Log.d("FrameAnalysis", "Bitmap: ${bitmap.width}x${bitmap.height}, config=${bitmap.config}")

    try {
        val result = OpenCVManager.detectDocument(bitmap)
        val isAligned = result.alignmentScore > 0.85f && (result.qualityMetrics?.blurScore ?: 0f) > 0.5f && (result.qualityMetrics?.glareScore ?: 1f) < 0.3f

        val newState = DocumentPreviewState(
            corners = result.corners?.map { android.graphics.Point(it.x.toInt(), it.y.toInt()) }?.toTypedArray(),
            isAligned = isAligned,
            alignmentScore = result.alignmentScore,
            qualityMetrics = result.qualityMetrics,
            frameColor = if (isAligned) 0xFF00FF00.toInt() else 0xFFFF0000.toInt(),
        )

        if (result.correctedBitmap != null) {
            result.correctedBitmap!!.recycle()
        }
        return newState
    } catch (e: Exception) {
        Log.e("FrameAnalysis", "Analysis failed", e)
        return null
    } finally {
        imageProxy.close()
        bitmap.recycle()
    }
}

fun mediaImageToBitmap(mediaImage: android.media.Image, rotationDegrees: Int): Bitmap {
    val width = mediaImage.width
    val height = mediaImage.height
    val yPlane = mediaImage.planes[0]
    val uPlane = mediaImage.planes[1]
    val vPlane = mediaImage.planes[2]

    val yRowStride = yPlane.rowStride
    val uvRowStride = uPlane.rowStride
    val uvPixelStride = uPlane.pixelStride

    val nv21 = ByteArray(width * height * 3 / 2)

    // Copy Y plane row by row, respecting rowStride
    val yBuf = yPlane.buffer
    for (row in 0 until height) {
        yBuf.position(row * yRowStride)
        yBuf.get(nv21, row * width, width)
    }

    // Copy interleaved VU for NV21
    val vBuf = vPlane.buffer
    val uBuf = uPlane.buffer
    val uvHeight = height / 2
    val uvWidth = width / 2
    var offset = width * height

    if (uvPixelStride == 2) {
        // U and V are already interleaved in memory (common on most devices).
        // V plane's buffer contains V,U,V,U,... — copy row by row.
        val rowBytes = kotlin.math.min(uvWidth * 2, vBuf.remaining().coerceAtLeast(0))
        for (row in 0 until uvHeight) {
            val rowStart = row * uvRowStride
            val remaining = vBuf.capacity() - rowStart
            val bytesToCopy = kotlin.math.min(uvWidth * 2, remaining)
            if (bytesToCopy <= 0) break
            vBuf.position(rowStart)
            vBuf.get(nv21, offset, bytesToCopy)
            // If last row had one fewer byte, fill the trailing byte
            if (bytesToCopy < uvWidth * 2) {
                nv21[offset + bytesToCopy] = nv21[offset + bytesToCopy - 2]
            }
            offset += uvWidth * 2
        }
    } else {
        for (row in 0 until uvHeight) {
            for (col in 0 until uvWidth) {
                val vIdx = row * uvRowStride + col * uvPixelStride
                val uIdx = row * uvRowStride + col * uvPixelStride
                nv21[offset++] = vBuf.get(vIdx)
                nv21[offset++] = uBuf.get(uIdx)
            }
        }
    }

    val yuvImage = android.graphics.YuvImage(nv21, android.graphics.ImageFormat.NV21, width, height, null)
    val out = java.io.ByteArrayOutputStream()
    yuvImage.compressToJpeg(android.graphics.Rect(0, 0, width, height), 90, out)
    val jpegBytes = out.toByteArray()
    val bitmap = BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.size)
        ?: throw IllegalStateException("Failed to decode JPEG from YUV conversion")

    // Apply rotation if needed
    return if (rotationDegrees != 0) {
        val matrix = android.graphics.Matrix()
        matrix.postRotate(rotationDegrees.toFloat())
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (rotated !== bitmap) bitmap.recycle()
        rotated
    } else {
        bitmap
    }
}

fun saveBitmapToFile(bitmap: Bitmap, file: File) {
    try {
        // Ensure the parent directory exists
        file.parentFile?.mkdirs()

        FileOutputStream(file).use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)
        }

        // Log file creation for debugging
        android.util.Log.d("CaptureScreen", "Saved image to: ${file.absolutePath}, exists: ${file.exists()}, size: ${file.length()}")
    } catch (e: Exception) {
        android.util.Log.e("CaptureScreen", "Failed to save bitmap to ${file.absolutePath}", e)
        throw e
    }
}

fun androidx.compose.ui.graphics.drawscope.DrawScope.drawDocumentOverlay(
    state: DocumentPreviewState,
    scanLineProgress: Float,
) {
    val width = size.width
    val height = size.height

    if (state.corners != null && state.corners!!.size == 4) {
        val path = Path()
        val corners = state.corners!!
        val bracketSize = (width * 0.08f)
        val strokeWidth = 4f
        val color = if (state.isAligned) Color.Green else Color.Red

        for (i in 0..3) {
            val pt = corners[i]
            val x = pt.x.toFloat()
            val y = pt.y.toFloat()

            when (i) {
                0 -> { path.moveTo(x, y + bracketSize); path.lineTo(x, y); path.lineTo(x + bracketSize, y) }
                1 -> { path.moveTo(x - bracketSize, y); path.lineTo(x, y); path.lineTo(x, y + bracketSize) }
                2 -> { path.moveTo(x, y - bracketSize); path.lineTo(x, y); path.lineTo(x - bracketSize, y) }
                3 -> { path.moveTo(x + bracketSize, y); path.lineTo(x, y); path.lineTo(x, y - bracketSize) }
            }
        }

        drawPath(
            path,
            color = color,
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round),
        )
    } else {
        val frameWidth = width * 0.8f
        val frameHeight = height * 0.6f
        val left = (width - frameWidth) / 2
        val top = (height - frameHeight) / 2

        val path = Path()
        val bracketSize = (width * 0.06f)
        val strokeWidth = 3f

        path.moveTo(left, top + bracketSize); path.lineTo(left, top); path.lineTo(left + bracketSize, top)
        path.moveTo(left + frameWidth - bracketSize, top); path.lineTo(left + frameWidth, top); path.lineTo(left + frameWidth, top + bracketSize)
        path.moveTo(left + frameWidth, top + frameHeight - bracketSize); path.lineTo(left + frameWidth, top + frameHeight); path.lineTo(left + frameWidth - bracketSize, top + frameHeight)
        path.moveTo(left + bracketSize, top + frameHeight); path.lineTo(left, top + frameHeight); path.lineTo(left, top + frameHeight - bracketSize)

        drawPath(
            path,
            color = Color.White.copy(alpha = 0.7f),
            style = Stroke(width = strokeWidth, cap = StrokeCap.Round),
        )
    }

    if (state.corners != null && state.corners!!.size == 4) {
        val corners = state.corners!!
        val leftX = corners.minByOrNull { it.x }?.x?.toFloat() ?: 0f
        val rightX = corners.maxByOrNull { it.x }?.x?.toFloat() ?: width
        val topY = corners.minByOrNull { it.y }?.y?.toFloat() ?: 0f
        val bottomY = corners.maxByOrNull { it.y }?.y?.toFloat() ?: height

        val lineY = topY + (bottomY - topY) * scanLineProgress

        drawLine(
            start = androidx.compose.ui.geometry.Offset(leftX, lineY),
            end = androidx.compose.ui.geometry.Offset(rightX, lineY),
            color = Color.Green.copy(alpha = 0.8f),
            strokeWidth = 2f,
        )

        drawRect(
            color = Color.Green.copy(alpha = 0.2f),
            topLeft = androidx.compose.ui.geometry.Offset(leftX, lineY - 8),
            size = androidx.compose.ui.geometry.Size(rightX - leftX, 16f),
        )
    }

    if (state.corners != null) {
        // Status text removed - using Compose overlay instead
    }
}

private val LIVENESS_PROMPT_IDS = listOf(
    R.string.liveness_turn_left,
    R.string.liveness_turn_right,
    R.string.liveness_blink,
    R.string.liveness_nod,
    R.string.liveness_hold_still,
)

enum class CaptureStep { DOCUMENT_FRONT, DOCUMENT_BACK, SELFIE, LIVENESS_CHECK, EXTRACTING, REVIEW_FIELDS, SUBMITTING, ERROR }

// One "document number" field regardless of document type — the backend's
// cross-check only ever reads the "passport_number" OCR key (see
// app/services/validation/cross_check.py), so a second, differently-keyed
// "document number" field would just be silently ignored server-side.
data class ExtractedFields(
    var name: String = "",
    var passportNumber: String = "",
    var nationality: String = "",
    var dateOfBirth: String = "",
    var dateOfExpiry: String = "",
    var gender: String = "",
)

private data class ExtractionBundle(
    val ocr: DocumentOcrExtractor.ExtractionResult,
    val documentEmbedding: List<Float>,
    val liveEmbedding: List<Float>,
    val faceDetection: com.pramaanai.officer.data.model.FaceDetectionResult,
    val tampering: com.pramaanai.officer.data.model.TamperingResult,
    val deepfake: com.pramaanai.officer.data.remote.DeepfakeResult,
    val barcode: DocumentBarcodeScanner.BarcodeResult? = null,
    val qualityIssues: List<String> = emptyList(),
    val allChecks: List<DocumentOcrExtractor.VerificationCheck> = emptyList(),
)

data class DocumentPreviewState(
    val corners: Array<android.graphics.Point>? = null,
    val isAligned: Boolean = false,
    val alignmentScore: Float = 0f,
    val qualityMetrics: OpenCVManager.QualityMetrics? = null,
    val frameColor: Int = 0xFFFF0000.toInt(),
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureScreen(
    repository: ScreeningRepository,
    documentType: String,
    checkpointCode: String?,
    onSubmitted: (screeningId: String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasCameraPermission = granted
    }
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
        OpenCVManager.init(context)
        FaceAligner.init(context)
        NeuralFaceEmbedding.init(context)
        AntiSpoofDetector.init(context)
    }

    var step by remember { mutableStateOf(CaptureStep.DOCUMENT_FRONT) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var imageAnalysis by remember { mutableStateOf<ImageAnalysis?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var documentFrontFile by remember { mutableStateOf<File?>(null) }
    var documentBackFile by remember { mutableStateOf<File?>(null) }
    var selfieFile by remember { mutableStateOf<File?>(null) }
    var correctedDocumentFrontBitmap by remember { mutableStateOf<Bitmap?>(null) }
    var correctedDocumentBackBitmap by remember { mutableStateOf<Bitmap?>(null) }
    val livenessPromptId = remember(step) { LIVENESS_PROMPT_IDS[Random.nextInt(LIVENESS_PROMPT_IDS.size)] }
    var selfieLensFacing by remember { mutableIntStateOf(CameraSelector.LENS_FACING_FRONT) }

    val previewState = remember { mutableStateOf(DocumentPreviewState()) }

    var scanLineProgress by remember { mutableStateOf(0f) }
    var scanLineDirection by remember { mutableStateOf(1f) }
    val scanLineAnimator = remember {
        object {
            var handler: Handler? = null
            fun start() {
                handler = Handler(Looper.getMainLooper())
                val runnable = object : Runnable {
                    override fun run() {
                        scanLineProgress += 0.02f * scanLineDirection
                        if (scanLineProgress >= 1f) {
                            scanLineProgress = 1f
                            scanLineDirection = -1f
                        } else if (scanLineProgress <= 0f) {
                            scanLineProgress = 0f
                            scanLineDirection = 1f
                        }
                        handler?.postDelayed(this, 16)
                    }
                }
                handler?.post(runnable)
            }
            fun stop() {
                handler?.removeCallbacksAndMessages(null)
                handler = null
            }
        }
    }

    var extractionConfidence by remember { mutableStateOf(0f) }
    var rawMrzText by remember { mutableStateOf<String?>(null) }
    var mrzLines by remember { mutableStateOf<List<String>>(emptyList()) }
    var detectedDocType by remember { mutableStateOf<String?>(null) }
    var documentEmbedding by remember { mutableStateOf<List<Float>?>(null) }
    var liveEmbedding by remember { mutableStateOf<List<Float>?>(null) }
    var faceDetectionResult by remember { mutableStateOf<com.pramaanai.officer.data.model.FaceDetectionResult?>(null) }
    var livenessResult by remember { mutableStateOf<com.pramaanai.officer.data.vision.LivenessAnalysisResult?>(null) }
    var tamperingResultState by remember { mutableStateOf<com.pramaanai.officer.data.model.TamperingResult?>(null) }
    var deepfakeResultState by remember { mutableStateOf<com.pramaanai.officer.data.remote.DeepfakeResult?>(null) }
    var verificationChecks by remember { mutableStateOf<List<DocumentOcrExtractor.VerificationCheck>>(emptyList()) }
    var extraFields by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var fields by remember { mutableStateOf(ExtractedFields()) }
    LaunchedEffect(step) {
        if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK || step == CaptureStep.SELFIE) {
            scanLineAnimator.start()
        } else {
            scanLineAnimator.stop()
        }
    }

    fun runExtraction() {
        val docFront = documentFrontFile ?: return
        val docBack = documentBackFile // Optional - may be null for some document types
        val selfie = selfieFile ?: return
        step = CaptureStep.EXTRACTING
        scope.launch {
            try {
                val bundle = withContext(Dispatchers.Default) {
                    val rawDocFrontBitmap = BitmapFactory.decodeFile(docFront.path)
                        ?: correctedDocumentFrontBitmap
                        ?: throw IllegalStateException("Could not decode document front image")
                    Log.d("CaptureScreen", "OCR input: file=${docFront.path}, size=${docFront.length()}, bitmap=${rawDocFrontBitmap.width}x${rawDocFrontBitmap.height}")

                    // Quality gate: detect document edges, check blur/glare,
                    // produce a perspective-corrected crop for better OCR
                    val qualityCheck = ImageQualityGate.check(rawDocFrontBitmap)
                    if (qualityCheck.issues.isNotEmpty()) {
                        Log.w("CaptureScreen", "Quality issues: ${qualityCheck.issues}")
                    }
                    val corrected = qualityCheck.correctedBitmap
                    val docFrontBitmap = if (corrected != null) {
                        val rawArea = rawDocFrontBitmap.width.toLong() * rawDocFrontBitmap.height
                        val corrArea = corrected.width.toLong() * corrected.height
                        if (corrArea < rawArea * 0.4) {
                            Log.w("CaptureScreen", "Corrected bitmap too small (${corrArea} vs ${rawArea}), using raw for OCR")
                            rawDocFrontBitmap
                        } else corrected
                    } else rawDocFrontBitmap

                    val docBackBitmap = docBack?.let {
                        BitmapFactory.decodeFile(it.path)
                            ?: correctedDocumentBackBitmap
                    }
                    val selfieBitmap = BitmapFactory.decodeFile(selfie.path)
                        ?: throw IllegalStateException("Could not decode selfie image")

                    // OCR on front side (uses corrected bitmap when available)
                    val ocr = DocumentOcrExtractor.recognize(docFrontBitmap)

                    // Face alignment before embedding — produces a normalized
                    // 112x112 face crop that improves embedding quality
                    val docFaceAligned = FaceAligner.alignFace(docFrontBitmap)
                    val selfieFaceAligned = FaceAligner.alignFace(selfieBitmap)

                    // Face embedding: try neural (MobileFaceNet) first,
                    // fall back to HOG if the model isn't loaded
                    val de: List<Float>
                    val le: List<Float>
                    val docAlignedBitmap = docFaceAligned.alignedFace
                    val selfieAlignedBitmap = selfieFaceAligned.alignedFace

                    if (NeuralFaceEmbedding.isAvailable() && docAlignedBitmap != null && selfieAlignedBitmap != null) {
                        val neuralDoc = NeuralFaceEmbedding.extract(docAlignedBitmap)
                        val neuralSelfie = NeuralFaceEmbedding.extract(selfieAlignedBitmap)
                        if (neuralDoc.embedding != null && neuralSelfie.embedding != null) {
                            de = neuralDoc.embedding
                            le = neuralSelfie.embedding
                            Log.d("CaptureScreen", "Using MobileFaceNet neural embeddings (128-d)")
                        } else {
                            de = FaceEmbedding.extractEmbedding(docFrontBitmap)
                            le = FaceEmbedding.extractEmbedding(selfieBitmap)
                            Log.d("CaptureScreen", "Neural inference failed, using HOG embeddings")
                        }
                    } else {
                        // HOG fallback — deterministic, no model file needed
                        de = FaceEmbedding.extractEmbedding(docAlignedBitmap ?: docFrontBitmap)
                        le = FaceEmbedding.extractEmbedding(selfieAlignedBitmap ?: selfieBitmap)
                        Log.d("CaptureScreen", "Using HOG face embeddings (aligned=${docAlignedBitmap != null})")
                    }

                    docAlignedBitmap?.recycle()
                    selfieAlignedBitmap?.recycle()

                    // Face presence/count/position on the live selfie
                    val fd = FaceDetectionAnalyzer.detect(selfieBitmap)

                    // On-device forensics
                    val tp = TamperingAnalyzer.analyze(docFrontBitmap)
                    val df = DeepfakeAnalyzer.analyze(selfieBitmap)

                    // QR/barcode scan
                    val barcode = try {
                        DocumentBarcodeScanner.scan(docFrontBitmap)
                    } catch (e: Exception) {
                        Log.w("CaptureScreen", "Barcode scan failed", e)
                        null
                    }

                    // Build comprehensive verification evidence
                    val allChecks = mutableListOf<DocumentOcrExtractor.VerificationCheck>()
                    fun vc(name: String, status: DocumentOcrExtractor.CheckStatus, detail: String) =
                        DocumentOcrExtractor.VerificationCheck(name, status, detail)
                    val PASS = DocumentOcrExtractor.CheckStatus.PASS
                    val WARN = DocumentOcrExtractor.CheckStatus.WARNING
                    val FAIL = DocumentOcrExtractor.CheckStatus.FAIL
                    val NA = DocumentOcrExtractor.CheckStatus.NOT_AVAILABLE

                    // Image quality checks
                    if (qualityCheck.issues.isEmpty()) {
                        allChecks.add(vc("Image quality", PASS, "Document image clear and well-lit"))
                    } else {
                        for (issue in qualityCheck.issues) {
                            allChecks.add(vc("Image quality", WARN, issue))
                        }
                    }

                    // OCR-generated checks (MRZ checksums, field completeness, expiry, etc.)
                    allChecks.addAll(ocr.verificationChecks)

                    // QR/barcode checks
                    if (barcode != null && barcode.found) {
                        allChecks.add(vc("QR/Barcode detected", PASS,
                            "${barcode.codes.size} code(s): ${barcode.codes.joinToString { it.format }}"))
                        allChecks.addAll(DocumentBarcodeScanner.crossCheckFields(barcode.fieldsFromCode, ocr.fields))
                    } else {
                        allChecks.add(vc("QR/Barcode scan", NA, "No machine-readable code found on document"))
                    }

                    // Face detection checks
                    when (fd.status) {
                        "SINGLE_FACE" -> allChecks.add(vc("Face detected", PASS, "Face found in live photo"))
                        "NO_FACE" -> allChecks.add(vc("Face detected", FAIL, "No face found in live photo"))
                        "MULTIPLE_FACES" -> allChecks.add(vc("Face detected", PASS, "Face found in live photo"))
                    }

                    // Face on document check
                    val docFaceResult = try { FaceDetectionAnalyzer.detect(docFrontBitmap) } catch (_: Exception) { null }
                    if (docFaceResult != null) {
                        when (docFaceResult.status) {
                            "SINGLE_FACE" -> allChecks.add(vc("Face on document", PASS, "Photo detected on document"))
                            "NO_FACE" -> allChecks.add(vc("Face on document", WARN, "No face photo found on document"))
                            "MULTIPLE_FACES" -> allChecks.add(vc("Face on document", PASS, "Photo detected on document"))
                        }
                    }

                    // On-device face similarity (cosine) between document and selfie embeddings
                    if (de.isNotEmpty() && le.isNotEmpty() && de.size == le.size) {
                        var dot = 0.0
                        var normA = 0.0
                        var normB = 0.0
                        for (i in de.indices) {
                            dot += de[i] * le[i]
                            normA += de[i] * de[i]
                            normB += le[i] * le[i]
                        }
                        val similarity = if (normA > 0 && normB > 0) dot / (Math.sqrt(normA) * Math.sqrt(normB)) else 0.0
                        val pct = (similarity * 100).toInt()
                        Log.d("CaptureScreen", "Face similarity: ${"%.4f".format(similarity)} ($pct%)")
                        when {
                            similarity >= 0.70 -> allChecks.add(vc("Face match (document ↔ selfie)", PASS, "Similarity $pct% — faces appear to match"))
                            similarity >= 0.55 -> allChecks.add(vc("Face match (document ↔ selfie)", WARN, "Similarity $pct% — low confidence, officer review recommended"))
                            else -> allChecks.add(vc("Face match (document ↔ selfie)", FAIL, "Similarity $pct% — faces do not appear to match"))
                        }
                    }

                    // Tampering checks
                    if (tp.tamperingRisk < 0.2) {
                        allChecks.add(vc("Document integrity check", PASS, "Document appears unaltered"))
                    } else if (tp.tamperingRisk < 0.5) {
                        allChecks.add(vc("Document integrity check", WARN, "Minor anomalies — officer review recommended"))
                    } else {
                        allChecks.add(vc("Document integrity check", FAIL, "Possible alteration detected — officer review recommended"))
                    }

                    // Deepfake/anti-spoof check
                    if (df.status == "ANALYZED") {
                        val dfScore = df.score ?: 0.0
                        if (dfScore < 0.3) {
                            allChecks.add(vc("Photo authenticity check", PASS, "Selfie appears genuine"))
                        } else if (dfScore < 0.6) {
                            allChecks.add(vc("Photo authenticity check", WARN, "Selfie quality uncertain — officer review recommended"))
                        } else {
                            allChecks.add(vc("Photo authenticity check", FAIL, "Photo may not be live — officer review recommended"))
                        }
                    }

                    // Server verification not yet done — will happen on submit
                    allChecks.add(vc("Registry verification", NA, "Pending — will check on submit"))

                    if (qualityCheck.correctedBitmap != null && qualityCheck.correctedBitmap !== rawDocFrontBitmap) {
                        qualityCheck.correctedBitmap.recycle()
                    }

                    ExtractionBundle(ocr, de, le, fd, tp, df, barcode, qualityCheck.issues, allChecks)
                }
                val ocrResult = bundle.ocr
                fields = ExtractedFields(
                    name = ocrResult.fields["name"] ?: "",
                    // Every document type's number (passport, ID, licence, permit) travels
                    // under this one key — it is what the backend looks up and de-duplicates on.
                    passportNumber = (ocrResult.fields["passport_number"]
                        ?: ocrResult.fields["document_number"]
                        ?: ocrResult.fields["aadhaar_number"]
                        ?: ocrResult.fields["citizenship_number"]
                        ?: ocrResult.fields["cid_number"]
                        ?: ocrResult.fields["licence_number"]
                        ?: ocrResult.fields["license_number"]
                        ?: ocrResult.fields["visa_number"]
                        ?: ocrResult.fields["permit_number"]
                        ?: ocrResult.fields["pan_number"]
                        ?: ocrResult.fields["voter_id"]
                        ?: "").replace(" ", ""),
                    nationality = ocrResult.fields["nationality"] ?: "",
                    dateOfBirth = ocrResult.fields["date_of_birth"] ?: "",
                    dateOfExpiry = ocrResult.fields["date_of_expiry"] ?: "",
                    gender = ocrResult.fields["gender"] ?: "",
                )
                extractionConfidence = ocrResult.confidence
                rawMrzText = ocrResult.mrzText ?: ocrResult.rawText
                mrzLines = ocrResult.mrzLines
                detectedDocType = ocrResult.detectedDocumentType
                documentEmbedding = bundle.documentEmbedding
                liveEmbedding = bundle.liveEmbedding
                faceDetectionResult = bundle.faceDetection
                tamperingResultState = bundle.tampering
                deepfakeResultState = bundle.deepfake
                verificationChecks = bundle.allChecks
                // Extra fields beyond the core 6 — doc-type-specific
                val coreKeys = setOf("name", "passport_number", "document_number", "nationality", "date_of_birth", "date_of_expiry", "gender")
                extraFields = ocrResult.fields.filterKeys { it !in coreKeys && !it.startsWith("qr_") }
                step = CaptureStep.REVIEW_FIELDS
            } catch (e: Exception) {
                errorMessage = "On-device extraction failed: ${e.message ?: e.toString()}"
                step = CaptureStep.ERROR
            }
        }
    }

    fun runLivenessCheck() {
        val selfie = selfieFile ?: return
        step = CaptureStep.LIVENESS_CHECK
        scope.launch {
            try {
                val liveness = withContext(Dispatchers.Default) {
                    val selfieBitmap = BitmapFactory.decodeFile(selfie.path)
                        ?: throw IllegalStateException("Could not decode selfie image")

                    try {
                        // Heuristic liveness (texture + temporal if multi-frame)
                        val heuristicResult = com.pramaanai.officer.data.vision.LivenessDetector.analyzeSingleFrame(selfieBitmap)

                        // Supplement with TFLite anti-spoof if model is available
                        val spoofResult = AntiSpoofDetector.detect(selfieBitmap)
                        if (spoofResult.available && spoofResult.isLive != null) {
                            val combinedScore = (heuristicResult.score + spoofResult.spoofScore) / 2.0
                            val combinedStatus = when {
                                combinedScore < 0.35 -> "LIVE"
                                combinedScore > 0.65 -> "SUSPECTED_SPOOF"
                                else -> "UNCERTAIN"
                            }
                            com.pramaanai.officer.data.vision.LivenessAnalysisResult(
                                status = combinedStatus,
                                score = combinedScore,
                                reason = "${heuristicResult.reason} | Anti-spoof (${spoofResult.method}): score=${String.format("%.3f", spoofResult.spoofScore)}",
                                temporalVariation = heuristicResult.temporalVariation,
                                textureQuality = heuristicResult.textureQuality,
                                framesAnalyzed = heuristicResult.framesAnalyzed,
                            )
                        } else {
                            heuristicResult
                        }
                    } catch (e: Exception) {
                        Log.e("CaptureScreen", "Liveness detection error", e)
                        com.pramaanai.officer.data.vision.LivenessAnalysisResult(
                            status = "UNCERTAIN",
                            score = 0.5,
                            reason = "Liveness check skipped due to error: ${e.message}",
                            temporalVariation = 0.0,
                            textureQuality = 0.5,
                            framesAnalyzed = 0
                        )
                    }
                }

                livenessResult = liveness

                // Always proceed (don't block on liveness for now)
                runExtraction()
            } catch (e: Exception) {
                Log.e("CaptureScreen", "Liveness check outer error", e)
                // Continue anyway
                runExtraction()
            }
        }
    }

    // No required-field gate here on purpose: OCR is best-effort and the
    // officer should never be forced to hand-type a field the scan missed.
    // A field the scan genuinely couldn't read just flows through as
    // whatever it is (blank, or the officer's own optional correction) —
    // the backend's own checks already say so explicitly and honestly
    // (e.g. "no date_of_birth field was extracted from the document")
    // rather than pretending a forced manual entry was ever real OCR.
    fun submit() {
        val front = documentFrontFile ?: return
        step = CaptureStep.SUBMITTING
        scope.launch {
            try {
                val docNum = fields.passportNumber.trim()
                val effectiveDocType = detectedDocType ?: documentType
                val ocrFields = buildMap {
                    put("name", fields.name.trim())
                    if (docNum.isNotBlank()) {
                        put("document_number", docNum)
                        when (effectiveDocType.uppercase()) {
                            "PASSPORT" -> put("passport_number", docNum)
                            "NATIONAL_ID" -> {
                                put("aadhaar_number", docNum)
                                put("citizenship_number", docNum)
                                put("cid_number", docNum)
                            }
                            "PAN_CARD" -> put("pan_number", docNum)
                            "VOTER_ID" -> put("voter_id", docNum)
                            "DRIVING_LICENCE", "DRIVING_LICENSE" -> {
                                put("licence_number", docNum)
                                put("license_number", docNum)
                            }
                            "VISA" -> put("visa_number", docNum)
                            "PERMIT" -> put("permit_number", docNum)
                            else -> put("passport_number", docNum)
                        }
                    }
                    put("nationality", fields.nationality.trim())
                    if (fields.dateOfBirth.isNotBlank()) put("date_of_birth", fields.dateOfBirth.trim())
                    if (fields.dateOfExpiry.isNotBlank()) put("date_of_expiry", fields.dateOfExpiry.trim())
                    if (fields.gender.isNotBlank()) put("gender", fields.gender.trim())
                    // Include all additional fields extracted on-device (date_of_issue,
                    // place_of_birth, issuing_authority, personal_number, cid_number, etc.)
                    for ((k, v) in extraFields) {
                        if (v.isNotBlank() && !containsKey(k)) put(k, v)
                    }
                }
                // Convert on-device liveness result to the DTO the backend expects
                val livenessDto = livenessResult?.let {
                    com.pramaanai.officer.data.remote.LivenessResult(
                        status = it.status,
                        score = it.score,
                        reason = it.reason,
                    )
                }
                val item = repository.submitScreening(
                    travelerName = fields.name,
                    documentType = documentType,
                    nationality = fields.nationality,
                    ocrFields = ocrFields,
                    ocrConfidence = extractionConfidence.toDouble(),
                    mrzText = rawMrzText,
                    documentFaceEmbedding = documentEmbedding,
                    liveFaceEmbedding = liveEmbedding,
                    documentImageFile = front,
                    documentBackImageFile = documentBackFile,
                    selfieImageFile = selfieFile,
                    faceDetectionResult = faceDetectionResult,
                    tamperingResult = tamperingResultState,
                    deepfakeResult = deepfakeResultState,
                    livenessResult = livenessDto,
                    detectedDocumentType = detectedDocType,
                )
                if (item.status == ScreeningStatus.OFFLINE_QUEUED) {
                    PendingSubmissionWorker.enqueue(context)
                    Toast.makeText(context, context.getString(R.string.toast_no_connection_queued), Toast.LENGTH_LONG).show()
                }
                onSubmitted(item.id)
            } catch (e: Exception) {
                errorMessage = e.message ?: e.toString()
                step = CaptureStep.ERROR
            }
        }
    }

    fun onImageReady(outputFile: File, label: String) {
        Toast.makeText(context, context.getString(R.string.toast_using_label, label), Toast.LENGTH_SHORT).show()
        when (step) {
            CaptureStep.DOCUMENT_FRONT -> {
                documentFrontFile = outputFile
                step = CaptureStep.DOCUMENT_BACK
            }
            CaptureStep.DOCUMENT_BACK -> {
                documentBackFile = outputFile
                step = CaptureStep.SELFIE
            }
            CaptureStep.SELFIE -> {
                selfieFile = outputFile
                runLivenessCheck()  // Run liveness check before extraction
            }
            else -> {
                // Should not happen
            }
        }
    }

    val pickMediaLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val fileName = when (step) {
            CaptureStep.DOCUMENT_FRONT -> "document_front_photo.jpg"
            CaptureStep.DOCUMENT_BACK -> "document_back_photo.jpg"
            CaptureStep.SELFIE -> "live_selfie.jpg"
            else -> "unknown.jpg"
        }
        val outputFile = File(context.cacheDir, fileName)
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(outputFile).use { output -> input.copyTo(output) }
            }
            onImageReady(outputFile, "uploaded photo")
        } catch (e: Exception) {
            Toast.makeText(context, context.getString(R.string.toast_upload_failed, e.message ?: ""), Toast.LENGTH_SHORT).show()
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.title_capture)) }) }) { padding ->
        GridPatternBackground(modifier = Modifier.padding(padding)) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
            val stepperStep = when (step) {
                CaptureStep.DOCUMENT_FRONT, CaptureStep.DOCUMENT_BACK, CaptureStep.SELFIE -> 1
                CaptureStep.LIVENESS_CHECK, CaptureStep.EXTRACTING -> 2
                CaptureStep.REVIEW_FIELDS -> 3
                else -> 4
            }
            if (step != CaptureStep.SUBMITTING && step != CaptureStep.ERROR) {
                WorkflowStepper(currentStep = stepperStep, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(12.dp))
            }
            if (!hasCameraPermission) {
                Text(stringResource(R.string.camera_permission_required))
                Spacer(Modifier.height(12.dp))
                Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                    Text(stringResource(R.string.grant_camera_permission))
                }
                return@Column
            }

            if (step == CaptureStep.LIVENESS_CHECK) {
                Column(
                    modifier = Modifier.fillMaxSize(),
                    verticalArrangement = Arrangement.Center,
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(64.dp),
                        color = AccentGreen,
                    )
                    Spacer(Modifier.height(24.dp))
                    Text(
                        "Checking photo…",
                        style = MaterialTheme.typography.titleMedium,
                        color = Color.White,
                    )
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Verifying this is a live person",
                        style = MaterialTheme.typography.bodyMedium,
                        color = Gray500,
                        textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                        modifier = Modifier.padding(horizontal = 32.dp),
                    )
                }
                return@Column
            }

            if (step == CaptureStep.EXTRACTING) {
                Spacer(Modifier.height(64.dp))
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.ocr_processing), style = MaterialTheme.typography.bodyMedium)
                return@Column
            }

            if (step == CaptureStep.REVIEW_FIELDS) {
                Text(stringResource(R.string.review_step_title), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.review_step_subtitle),
                    style = MaterialTheme.typography.bodySmall,
                    color = Gray600,
                )
                Spacer(Modifier.height(12.dp))
                // Scrolls in its own weighted region so the action buttons
                // below stay on-screen on any display size.
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState()),
                ) {
                    // Document photos
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                        PhotoTile(stringResource(R.string.capture_label_front), documentFrontFile?.path, Modifier.weight(1f), wholeImage = true)
                        PhotoTile(stringResource(R.string.capture_label_back), documentBackFile?.path, Modifier.weight(1f), wholeImage = true)
                        PhotoTile(stringResource(R.string.capture_label_live), selfieFile?.path, Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(12.dp))
                    ConfidenceTag(confidence = extractionConfidence.toDouble())
                    Spacer(Modifier.height(4.dp))

                    // Document type mismatch warning
                    val mismatchMessage = detectDocTypeMismatch(documentType, detectedDocType)
                    if (mismatchMessage != null) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            mismatchMessage,
                            style = MaterialTheme.typography.bodySmall,
                            color = DestructiveRed,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(DestructiveRed.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                                .padding(12.dp),
                        )
                        Spacer(Modifier.height(8.dp))
                    }

                    ExtractedFieldRow(stringResource(R.string.field_full_name), fields.name)
                    ExtractedFieldRow(stringResource(R.string.field_document_number), fields.passportNumber)
                    ExtractedFieldRow(stringResource(R.string.field_nationality), fields.nationality)
                    ExtractedFieldRow(stringResource(R.string.field_date_of_birth), fields.dateOfBirth)
                    ExtractedFieldRow(stringResource(R.string.field_gender), fields.gender)
                    ExtractedFieldRow(stringResource(R.string.field_date_of_expiry), fields.dateOfExpiry)
                    // Document-type-specific extra fields
                    if (extraFields.isNotEmpty()) {
                        for ((key, value) in extraFields) {
                            val label = key.replace("_", " ").replaceFirstChar { it.uppercase() }
                            ExtractedFieldRow(label, value)
                        }
                    }

                    // Detected document type
                    if (detectedDocType != null) {
                        Spacer(Modifier.height(8.dp))
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(AccentGreen.copy(alpha = 0.10f), RoundedCornerShape(8.dp))
                                .padding(12.dp),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("Detected type:", style = MaterialTheme.typography.labelMedium, color = Gray600)
                            Text(
                                detectedDocType!!.replace("_", " "),
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = androidx.compose.ui.text.font.FontWeight.Bold,
                                color = AccentGreen,
                            )
                        }
                    }

                    // MRZ section
                    if (mrzLines.isNotEmpty()) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            "Machine-Readable Zone (MRZ)",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = androidx.compose.ui.text.font.FontWeight.SemiBold,
                            color = Gray600,
                        )
                        Spacer(Modifier.height(6.dp))
                        Text(
                            mrzLines.joinToString("\n"),
                            style = MaterialTheme.typography.labelSmall,
                            fontFamily = FontFamily.Monospace,
                            color = AccentGreen,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(BackgroundDark, RoundedCornerShape(8.dp))
                                .padding(10.dp),
                        )
                    }

                    if (listOf(fields.name, fields.passportNumber, fields.nationality, fields.dateOfBirth, fields.dateOfExpiry).all { it.isBlank() }) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            stringResource(R.string.capture_nothing_read),
                            style = MaterialTheme.typography.bodySmall,
                            color = WarningAmber,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(WarningAmber.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                                .padding(12.dp),
                        )
                    }
                    // Verification evidence section
                    if (verificationChecks.isNotEmpty()) {
                        Spacer(Modifier.height(16.dp))
                        VerificationEvidenceSection(verificationChecks)
                    }

                    Spacer(Modifier.height(12.dp))
                    Text(
                        stringResource(R.string.capture_verify_explanation),
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray500,
                    )
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                    OutlinedButton(
                        onClick = {
                            documentFrontFile = null
                            documentBackFile = null
                            selfieFile = null
                            correctedDocumentFrontBitmap = null
                            correctedDocumentBackBitmap = null
                            fields = ExtractedFields()
                            step = CaptureStep.DOCUMENT_FRONT
                        },
                        modifier = Modifier.weight(1f).height(52.dp),
                    ) { Text(stringResource(R.string.button_rescan)) }
                    Button(
                        onClick = { submit() },
                        modifier = Modifier.weight(1.6f).height(52.dp),
                        colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                            containerColor = AccentGreen,
                            contentColor = BackgroundDark,
                        ),
                    ) { Text(stringResource(R.string.button_verify_registry), fontWeight = FontWeight.SemiBold) }
                }
                Spacer(Modifier.height(16.dp))
                return@Column
            }

            if (step == CaptureStep.SUBMITTING) {
                Spacer(Modifier.height(64.dp))
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text(stringResource(R.string.capture_submitting), style = MaterialTheme.typography.bodyMedium)
                return@Column
            }

            if (step == CaptureStep.ERROR) {
                Spacer(Modifier.height(64.dp))
                Text(stringResource(R.string.capture_submission_failed), style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text(errorMessage.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(16.dp))
                Button(onClick = { submit() }) { Text(stringResource(R.string.capture_retry)) }
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = {
                    documentFrontFile = null
                    documentBackFile = null
                    selfieFile = null
                    correctedDocumentFrontBitmap = null
                    correctedDocumentBackBitmap = null
                    fields = ExtractedFields()
                    step = CaptureStep.DOCUMENT_FRONT
                }) { Text(stringResource(R.string.start_over)) }
                return@Column
            }

            when (step) {
                CaptureStep.DOCUMENT_FRONT -> {
                    Text(stringResource(R.string.capture_step_1_title), style = MaterialTheme.typography.titleMedium)
                    Text(
                        stringResource(R.string.capture_step_1_desc),
                        style = MaterialTheme.typography.bodyMedium
                    )
                    if (previewState.value.qualityMetrics != null) {
                        QualityIndicatorsRow(metrics = previewState.value.qualityMetrics!!)
                    }
                }
                CaptureStep.DOCUMENT_BACK -> {
                    Text(stringResource(R.string.capture_step_2_title), style = MaterialTheme.typography.titleMedium)
                    Text(
                        stringResource(R.string.capture_step_2_desc),
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        stringResource(R.string.skip_back_hint),
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray500,
                    )
                    if (previewState.value.qualityMetrics != null) {
                        QualityIndicatorsRow(metrics = previewState.value.qualityMetrics!!)
                    }
                }
                CaptureStep.SELFIE -> {
                    Text(stringResource(R.string.capture_step_3_title), style = MaterialTheme.typography.titleMedium)
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                        Text(
                            text = stringResource(livenessPromptId),
                            modifier = Modifier.padding(16.dp),
                            style = MaterialTheme.typography.headlineSmall,
                        )
                    }
                }
                else -> Unit
            }

            Spacer(Modifier.height(12.dp))

            EnhancedCameraPreview(
                // weight(1f), not fillMaxSize() — inside a plain (non-
                // scrollable) Column, fillMaxSize() claims the entire
                // remaining constraint space and pushes the capture
                // button (and the debug upload button) off the bottom
                // of the screen, unreachable. weight(1f) makes Column
                // lay out the fixed-height button first and only give
                // the preview whatever's left.
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                lensFacing = if (step == CaptureStep.SELFIE) selfieLensFacing else CameraSelector.LENS_FACING_BACK,
                onImageCaptureReady = { imageCapture = it },
                onAnalysisReady = { imageAnalysis = it },
                step = step,
                previewState = previewState,
                scanLineProgress = scanLineProgress,
                onAutoCapture = { /* manual capture only */ },
            )

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = {
                    val capture = imageCapture ?: return@Button
                    val fileName = when (step) {
                        CaptureStep.DOCUMENT_FRONT -> "document_front_photo.jpg"
                        CaptureStep.DOCUMENT_BACK -> "document_back_photo.jpg"
                        CaptureStep.SELFIE -> "live_selfie.jpg"
                        else -> "unknown.jpg"
                    }
                    val outputFile = File(context.cacheDir, fileName)
                    val outputOptions = ImageCapture.OutputFileOptions.Builder(outputFile).build()
                    capture.takePicture(
                        outputOptions,
                        ContextCompat.getMainExecutor(context),
                        object : ImageCapture.OnImageSavedCallback {
                            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                                onImageReady(outputFile, "Saved: ${outputFile.name}")
                            }

                            override fun onError(exception: ImageCaptureException) {
                                Toast.makeText(context, "Capture failed: ${exception.message}", Toast.LENGTH_SHORT).show()
                            }
                        },
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                    containerColor = if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK)
                        AccentGreen
                    else
                        MaterialTheme.colorScheme.surfaceContainerHighest,
                    contentColor = if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK)
                        BackgroundDark
                    else
                        MaterialTheme.colorScheme.onSurface,
                ),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Filled.FlashOn,
                        contentDescription = null,
                        modifier = Modifier.size(24.dp),
                        tint = if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK) BackgroundDark else MaterialTheme.colorScheme.onSurface,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        when (step) {
                            CaptureStep.DOCUMENT_FRONT -> stringResource(R.string.capture_document_front)
                            CaptureStep.DOCUMENT_BACK -> stringResource(R.string.capture_document_back)
                            CaptureStep.SELFIE -> stringResource(R.string.capture_selfie)
                            else -> stringResource(R.string.capture_generic)
                        },
                        style = MaterialTheme.typography.labelLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }

            if (step == CaptureStep.SELFIE) {
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = {
                        selfieLensFacing = if (selfieLensFacing == CameraSelector.LENS_FACING_FRONT)
                            CameraSelector.LENS_FACING_BACK
                        else
                            CameraSelector.LENS_FACING_FRONT
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
                ) {
                    Text(stringResource(R.string.capture_flip_camera))
                }
            }

            // A real, always-available fallback — not just a debug shortcut —
            // for a document already photographed on another device, or a
            // live camera that's unavailable/unreliable at this checkpoint.
            // Goes through the same onImageReady path as a live capture, so
            // on-device OCR/quality checks run identically either way.
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    pickMediaLauncher.launch(
                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                    )
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(48.dp),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
            ) {
                Text(when (step) {
                    CaptureStep.DOCUMENT_FRONT -> stringResource(R.string.upload_document_front)
                    CaptureStep.DOCUMENT_BACK -> stringResource(R.string.upload_document_back)
                    CaptureStep.SELFIE -> stringResource(R.string.upload_selfie)
                    else -> stringResource(R.string.upload_generic)
                })
            }
            if (step == CaptureStep.DOCUMENT_BACK) {
                Spacer(Modifier.height(8.dp))
                OutlinedButton(
                    onClick = {
                        documentBackFile = null
                        step = CaptureStep.SELFIE
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(48.dp),
                    shape = androidx.compose.foundation.shape.RoundedCornerShape(12.dp),
                ) {
                    Text(stringResource(R.string.skip_back_side))
                }
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}
}

private val DOC_TYPE_DISPLAY_NAMES = mapOf(
    "NATIONAL_ID" to "National ID / Aadhaar",
    "DRIVING_LICENCE" to "Driving Licence",
    "PASSPORT" to "Passport",
    "VISA" to "Visa",
    "PERMIT" to "Permit",
    "PAN_CARD" to "PAN Card",
    "VOTER_ID" to "Voter ID",
    "CITIZENSHIP_CERTIFICATE" to "Citizenship Certificate",
)

private val SELECTED_TO_DETECTED = mapOf(
    "national_id" to setOf("NATIONAL_ID"),
    "passport" to setOf("PASSPORT"),
    "driving_licence" to setOf("DRIVING_LICENCE"),
    "visa" to setOf("VISA"),
    "permit" to setOf("PERMIT"),
)

private fun detectDocTypeMismatch(selectedType: String, detectedType: String?): String? {
    if (detectedType == null) return null
    val expectedSet = SELECTED_TO_DETECTED[selectedType.lowercase()] ?: return null
    if (detectedType.uppercase() in expectedSet) return null
    val detectedName = DOC_TYPE_DISPLAY_NAMES[detectedType.uppercase()] ?: detectedType
    val selectedName = DOC_TYPE_DISPLAY_NAMES[expectedSet.first()] ?: selectedType
    return "Document mismatch: This looks like a $detectedName, but you selected $selectedName. " +
            "Go back and select the correct document type for better results."
}

@Composable
private fun VerificationEvidenceSection(checks: List<DocumentOcrExtractor.VerificationCheck>) {
    val passCount = checks.count { it.status == DocumentOcrExtractor.CheckStatus.PASS }
    val warnCount = checks.count { it.status == DocumentOcrExtractor.CheckStatus.WARNING }
    val failCount = checks.count { it.status == DocumentOcrExtractor.CheckStatus.FAIL }
    val naCount = checks.count { it.status == DocumentOcrExtractor.CheckStatus.NOT_AVAILABLE }

    val overallColor = when {
        failCount > 0 -> DestructiveRed
        warnCount > 0 -> WarningAmber
        else -> AccentGreen
    }
    val overallLabel = when {
        failCount > 0 -> "REVIEW REQUIRED"
        warnCount > 0 -> "CAUTION"
        else -> "CHECKS PASSED"
    }

    Column(modifier = Modifier.fillMaxWidth()) {
        // Summary header
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .background(overallColor.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Text(
                "On-device verification",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
            )
            Text(
                overallLabel,
                style = MaterialTheme.typography.labelMedium,
                color = overallColor,
                fontWeight = FontWeight.Bold,
            )
        }

        Spacer(Modifier.height(4.dp))

        // Counts row
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            CheckCountChip(passCount, "Pass", AccentGreen)
            CheckCountChip(warnCount, "Warn", WarningAmber)
            CheckCountChip(failCount, "Fail", DestructiveRed)
            if (naCount > 0) CheckCountChip(naCount, "N/A", Gray500)
        }

        Spacer(Modifier.height(8.dp))

        // Individual checks — show FAIL and WARNING first, then PASS, then NOT_AVAILABLE
        val sorted = checks.sortedBy { check ->
            when (check.status) {
                DocumentOcrExtractor.CheckStatus.FAIL -> 0
                DocumentOcrExtractor.CheckStatus.WARNING -> 1
                DocumentOcrExtractor.CheckStatus.PASS -> 2
                DocumentOcrExtractor.CheckStatus.NOT_AVAILABLE -> 3
            }
        }
        for (check in sorted) {
            VerificationCheckRow(check)
        }
    }
}

@Composable
private fun CheckCountChip(count: Int, label: String, color: androidx.compose.ui.graphics.Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(color, CircleShape),
        )
        Spacer(Modifier.width(4.dp))
        Text(
            "$count $label",
            style = MaterialTheme.typography.labelSmall,
            color = color,
        )
    }
}

@Composable
private fun VerificationCheckRow(check: DocumentOcrExtractor.VerificationCheck) {
    val (icon, color) = when (check.status) {
        DocumentOcrExtractor.CheckStatus.PASS -> "✓" to AccentGreen
        DocumentOcrExtractor.CheckStatus.WARNING -> "⚠" to WarningAmber
        DocumentOcrExtractor.CheckStatus.FAIL -> "✗" to DestructiveRed
        DocumentOcrExtractor.CheckStatus.NOT_AVAILABLE -> "—" to Gray500
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Text(
            icon,
            color = color,
            style = MaterialTheme.typography.labelMedium,
            modifier = Modifier.width(20.dp),
        )
        Column(modifier = Modifier.weight(1f)) {
            Text(
                check.name,
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(
                check.detail,
                style = MaterialTheme.typography.bodySmall,
                color = Gray600,
            )
        }
    }
}