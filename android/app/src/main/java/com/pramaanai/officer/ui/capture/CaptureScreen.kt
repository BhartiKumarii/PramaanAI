package com.pramaanai.officer.ui.capture

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
import com.pramaanai.officer.data.vision.DocumentOcrExtractor
import com.pramaanai.officer.data.vision.FaceDetectionAnalyzer
import com.pramaanai.officer.data.vision.FaceEmbedding
import com.pramaanai.officer.data.vision.OpenCVManager
import com.pramaanai.officer.ui.components.ConfidenceTag
import com.pramaanai.officer.ui.components.GridPatternBackground
import com.pramaanai.officer.ui.components.WorkflowStepper
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
        QualityIndicator("Blur", metrics.blurScore, 0.7f),
        QualityIndicator("Glare", 1f - metrics.glareScore, 0.7f),
        QualityIndicator("Lighting", metrics.lightingScore, 0.6f),
        QualityIndicator("Shadows", 1f - metrics.shadowScore, 0.6f),
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
                val analysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setTargetResolution(android.util.Size(640, 480))
                    .build()
                    .also { imgAnalysis ->
                        imgAnalysis.setAnalyzer(ContextCompat.getMainExecutor(context)) { imageProxy ->
                            val newState = analyzeFrame(imageProxy, step, onAutoCapture)
                            if (newState != null) {
                                previewState.value = newState
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

    val mediaImage = imageProxy.image ?: return null
    val bitmap = mediaImageToBitmap(mediaImage, imageProxy.imageInfo.rotationDegrees)

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

        if (isAligned && result.correctedBitmap != null) {
            onAutoCapture(result.correctedBitmap!!)
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
    val planes = mediaImage.planes
    val yBuffer = planes[0].buffer
    val uBuffer = planes[1].buffer
    val vBuffer = planes[2].buffer

    val ySize = yBuffer.remaining()
    val uSize = uBuffer.remaining()
    val vSize = vBuffer.remaining()

    val nv21 = ByteArray(ySize + uSize + vSize)
    yBuffer.get(nv21, 0, ySize)
    vBuffer.get(nv21, ySize, vSize)
    uBuffer.get(nv21, ySize + vSize, uSize)

    val yuvImage = android.graphics.YuvImage(nv21, android.graphics.ImageFormat.NV21, mediaImage.width, mediaImage.height, null)
    val out = java.io.ByteArrayOutputStream()
    yuvImage.compressToJpeg(android.graphics.Rect(0, 0, mediaImage.width, mediaImage.height), 90, out)
    val imageBytes = out.toByteArray()
    return BitmapFactory.decodeByteArray(imageBytes, 0, imageBytes.size)
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

private val LIVENESS_PROMPTS = listOf(
    "Turn your head slowly to the left",
    "Turn your head slowly to the right",
    "Blink twice",
    "Nod your head once",
    "Look directly at the camera and hold still",
)

enum class CaptureStep { DOCUMENT_FRONT, DOCUMENT_BACK, SELFIE, EXTRACTING, REVIEW_FIELDS, SUBMITTING, ERROR }

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
    val livenessPrompt = remember(step) { LIVENESS_PROMPTS[Random.nextInt(LIVENESS_PROMPTS.size)] }

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
                    val docFrontBitmap = correctedDocumentFrontBitmap ?: BitmapFactory.decodeFile(docFront.path)
                    val docBackBitmap = docBack?.let { correctedDocumentBackBitmap ?: BitmapFactory.decodeFile(it.path) }
                    val selfieBitmap = BitmapFactory.decodeFile(selfie.path)

                    // OCR on front side (main document data)
                    val ocr = DocumentOcrExtractor.recognize(docFrontBitmap)

                    // Face embedding from front side photo
                    val de = FaceEmbedding.extractEmbedding(docFrontBitmap)
                    val le = FaceEmbedding.extractEmbedding(selfieBitmap)

                    // Real face presence/count/position over the live
                    // selfie — the actual "multiple faces" / "no face"
                    // fraud/quality signal, distinct from the embedding
                    // match/no-match comparison above.
                    val fd = FaceDetectionAnalyzer.detect(selfieBitmap)
                    ExtractionBundle(ocr, de, le, fd)
                }
                val ocrResult = bundle.ocr
                fields = ExtractedFields(
                    name = ocrResult.fields["name"] ?: "",
                    // Every document type's number (passport, ID, licence, permit) travels
                    // under this one key — it is what the backend looks up and de-duplicates on.
                    passportNumber = (ocrResult.fields["passport_number"] ?: ocrResult.fields["document_number"] ?: "")
                        .replace(" ", ""),
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
                step = CaptureStep.REVIEW_FIELDS
            } catch (e: Exception) {
                errorMessage = "On-device extraction failed: ${e.message ?: e.toString()}"
                step = CaptureStep.ERROR
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
                val ocrFields = buildMap {
                    put("name", fields.name.trim())
                    if (fields.passportNumber.isNotBlank()) put("passport_number", fields.passportNumber.trim())
                    put("nationality", fields.nationality.trim())
                    if (fields.dateOfBirth.isNotBlank()) put("date_of_birth", fields.dateOfBirth.trim())
                    if (fields.dateOfExpiry.isNotBlank()) put("date_of_expiry", fields.dateOfExpiry.trim())
                    if (fields.gender.isNotBlank()) put("gender", fields.gender.trim())
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
                runExtraction()
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
                CaptureStep.EXTRACTING -> 2
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

            if (step == CaptureStep.EXTRACTING) {
                Spacer(Modifier.height(64.dp))
                CircularProgressIndicator()
                Spacer(Modifier.height(16.dp))
                Text("Reading document on-device (OCR + MRZ + face signature)…", style = MaterialTheme.typography.bodyMedium)
                return@Column
            }

            if (step == CaptureStep.REVIEW_FIELDS) {
                Text("Step 3 — Review what was read", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Nothing is typed in by hand. These values were read from the document on this device.",
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
                        PhotoTile("Document front", documentFrontFile?.path, Modifier.weight(1f), wholeImage = true)
                        PhotoTile("Document back", documentBackFile?.path, Modifier.weight(1f), wholeImage = true)
                        PhotoTile("Live capture", selfieFile?.path, Modifier.weight(1f))
                    }
                    Spacer(Modifier.height(12.dp))
                    ConfidenceTag(confidence = extractionConfidence.toDouble())
                    Spacer(Modifier.height(4.dp))
                    ExtractedFieldRow("Full name", fields.name)
                    ExtractedFieldRow("Document number", fields.passportNumber)
                    ExtractedFieldRow("Nationality", fields.nationality)
                    ExtractedFieldRow("Date of birth", fields.dateOfBirth)
                    ExtractedFieldRow("Gender", fields.gender)
                    ExtractedFieldRow("Date of expiry", fields.dateOfExpiry)
                    if (listOf(fields.name, fields.passportNumber, fields.nationality, fields.dateOfBirth, fields.dateOfExpiry).all { it.isBlank() }) {
                        Spacer(Modifier.height(12.dp))
                        Text(
                            "Nothing could be read from this photo. Rescan with the document's data page " +
                                "filling the frame, flat and in good light.",
                            style = MaterialTheme.typography.bodySmall,
                            color = WarningAmber,
                            modifier = Modifier
                                .fillMaxWidth()
                                .background(WarningAmber.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                                .padding(12.dp),
                        )
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(
                        "Verifying checks these values against the registry and runs the document checks. " +
                            "Anything that doesn't line up is flagged for your review.",
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
                Text("Submitting to screening backend…", style = MaterialTheme.typography.bodyMedium)
                return@Column
            }

            if (step == CaptureStep.ERROR) {
                Spacer(Modifier.height(64.dp))
                Text("Screening submission failed", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(8.dp))
                Text(errorMessage.orEmpty(), style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(16.dp))
                Button(onClick = { submit() }) { Text("Retry") }
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = {
                    documentFrontFile = null
                    documentBackFile = null
                    selfieFile = null
                    correctedDocumentFrontBitmap = null
                    correctedDocumentBackBitmap = null
                    fields = ExtractedFields()
                    step = CaptureStep.DOCUMENT_FRONT
                }) { Text("Start over") }
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
                    if (previewState.value.qualityMetrics != null) {
                        QualityIndicatorsRow(metrics = previewState.value.qualityMetrics!!)
                    }
                }
                CaptureStep.SELFIE -> {
                    Text(stringResource(R.string.capture_step_3_title), style = MaterialTheme.typography.titleMedium)
                    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)) {
                        Text(
                            text = livenessPrompt,
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
                lensFacing = if (step == CaptureStep.SELFIE) CameraSelector.LENS_FACING_FRONT else CameraSelector.LENS_FACING_BACK,
                onImageCaptureReady = { imageCapture = it },
                onAnalysisReady = { imageAnalysis = it },
                step = step,
                previewState = previewState,
                scanLineProgress = scanLineProgress,
                onAutoCapture = { bitmap ->
                    when (step) {
                        CaptureStep.DOCUMENT_FRONT -> {
                            correctedDocumentFrontBitmap = bitmap
                            val outputFile = File(context.cacheDir, "document_front_photo.jpg")
                            saveBitmapToFile(bitmap, outputFile)
                            onImageReady(outputFile, "Auto-captured document front")
                        }
                        CaptureStep.DOCUMENT_BACK -> {
                            correctedDocumentBackBitmap = bitmap
                            val outputFile = File(context.cacheDir, "document_back_photo.jpg")
                            saveBitmapToFile(bitmap, outputFile)
                            onImageReady(outputFile, "Auto-captured document back")
                        }
                        else -> {
                            // Selfies don't auto-capture
                        }
                    }
                },
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
                    containerColor = if (previewState.value.isAligned && (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK))
                        MaterialTheme.colorScheme.primary
                    else if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK)
                        AccentGreen.copy(alpha = 0.8f)
                    else
                        MaterialTheme.colorScheme.surfaceContainerHighest,
                    contentColor = if (previewState.value.isAligned && (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK))
                        MaterialTheme.colorScheme.onPrimary
                    else if (step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK)
                        BackgroundDark
                    else
                        MaterialTheme.colorScheme.onSurface,
                ),
                shape = androidx.compose.foundation.shape.RoundedCornerShape(16.dp),
            ) {
                if ((step == CaptureStep.DOCUMENT_FRONT || step == CaptureStep.DOCUMENT_BACK) && previewState.value.isAligned) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(Icons.Filled.FlashOn, contentDescription = null, modifier = Modifier.size(24.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Auto-capturing…", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                    }
                } else {
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
                                CaptureStep.DOCUMENT_FRONT -> "Capture document front"
                                CaptureStep.DOCUMENT_BACK -> "Capture document back"
                                CaptureStep.SELFIE -> "Capture selfie"
                                else -> "Capture"
                            },
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
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
                    CaptureStep.DOCUMENT_FRONT -> "Upload document front instead"
                    CaptureStep.DOCUMENT_BACK -> "Upload document back instead"
                    CaptureStep.SELFIE -> "Upload selfie photo instead"
                    else -> "Upload photo instead"
                })
            }
            Spacer(Modifier.height(16.dp))
        }
    }
}
}