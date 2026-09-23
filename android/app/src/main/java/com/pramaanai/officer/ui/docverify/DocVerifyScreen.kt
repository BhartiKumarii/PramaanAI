package com.pramaanai.officer.ui.docverify

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import com.pramaanai.officer.ui.theme.ForegroundLight
import androidx.compose.runtime.key
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.filled.Cameraswitch
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.DocumentScanner
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.pramaanai.officer.R
import com.pramaanai.officer.ui.tour.tourSection
import com.pramaanai.officer.ui.tour.tourAnchor
import com.pramaanai.officer.data.docverify.CheckDetail
import com.pramaanai.officer.data.docverify.DocVerifyRepository
import com.pramaanai.officer.data.docverify.LocalCheck
import com.pramaanai.officer.data.docverify.OnDeviceRegionDetector
import com.pramaanai.officer.data.docverify.VerificationOutcome
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.ChartBlue
import com.pramaanai.officer.ui.theme.ChartPurple
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.MutedForeground
import com.pramaanai.officer.ui.theme.SecondaryDark
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import kotlinx.coroutines.launch

/* Officer workflow for document verification.
 *  Capture → on-device YOLO region detection → review regions + border
 *  → ONE HTTPS request with the region crops → structured result
 *  (or OFFLINE VERIFICATION: encrypted queue, synced automatically).
 * Status is always icon + text + colour, never colour alone. */

private sealed class Step {
    data object Capture : Step()
    data class Working(val message: String) : Step()
    data class Review(val analysis: DocVerifyRepository.Analysis) : Step()
    data class Face(val analysis: DocVerifyRepository.Analysis) : Step()
    data class Verified(val analysis: DocVerifyRepository.Analysis, val outcome: VerificationOutcome, val face: Bitmap? = null) : Step()
    data class Queued(val analysis: DocVerifyRepository.Analysis, val checks: List<LocalCheck>, val reason: String) : Step()
    data class Failed(val message: String) : Step()
}

private data class StatusUi(val label: String, val color: Color, val icon: ImageVector)

private fun statusUi(status: String) = when (status) {
    "PASS" -> StatusUi("Verified", SuccessGreen, Icons.Filled.CheckCircle)
    "REVIEW_REQUIRED" -> StatusUi("Review required", WarningAmber, Icons.Filled.Warning)
    "FAIL" -> StatusUi("Check failed", DestructiveRed, Icons.Filled.Error)
    "REGISTRY_NOT_AVAILABLE" -> StatusUi("Registry not available", ChartBlue, Icons.Filled.Info)
    "OFFICIAL_VERIFICATION_REQUIRED" -> StatusUi("Official verification required", ChartBlue, Icons.Filled.Info)
    "REFERENCE_NOT_AVAILABLE" -> StatusUi("No reference available", MutedForeground, Icons.Filled.Info)
    "NOT_APPLICABLE" -> StatusUi("Not applicable", MutedForeground, Icons.Filled.Info)
    else -> StatusUi("Not verified", MutedForeground, Icons.Filled.Info)
}

private val REGION_COLOURS = mapOf(
    "document" to MutedForeground, "photograph" to SuccessGreen, "mrz" to ChartBlue, "qr_code" to ChartPurple,
    "barcode" to ChartPurple, "stamp" to WarningAmber, "yellow_gold_feature" to Color(0xFFE8C547),
    "problem" to DestructiveRed,
)

private fun humanize(s: String) = s.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }

// ---------------------------------------------------------------- entry points

/** Dashboard hero card — the primary officer action. */
@Composable
fun VerifyDocumentCta(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var pending by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) { pending = DocVerifyRepository(context.applicationContext).pendingCount() }
    // The officer's primary action on the dashboard.
    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = AccentGreen),
        shape = RoundedCornerShape(14.dp),
    ) {
        Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(48.dp).background(BackgroundDark.copy(alpha = 0.12f), RoundedCornerShape(12.dp)),
                contentAlignment = Alignment.Center) {
                Icon(Icons.Filled.DocumentScanner, contentDescription = null, tint = BackgroundDark, modifier = Modifier.size(28.dp))
            }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.dashboard_verify_document), style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold, color = BackgroundDark)
                Text(stringResource(R.string.dashboard_verify_document_sub), style = MaterialTheme.typography.bodySmall,
                    color = BackgroundDark.copy(alpha = 0.75f))
            }
            if (pending > 0) {
                Box(Modifier.background(BackgroundDark, RoundedCornerShape(10.dp)).padding(horizontal = 8.dp, vertical = 4.dp)) {
                    Text("$pending offline", color = AccentGreen, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
fun DocVerifyScreen(padding: PaddingValues) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    val scope = rememberCoroutineScope()
    var step by remember { mutableStateOf<Step>(Step.Capture) }
    var route by remember { mutableStateOf(com.pramaanai.officer.data.local.AppSettings.defaultRoute(context)) }
    var direction by remember { mutableStateOf<String?>(null) }
    var pending by remember { mutableIntStateOf(0) }
    LaunchedEffect(step) { pending = repo.pendingCount() }

    fun submit(analysis: DocVerifyRepository.Analysis, face: Bitmap?) {
        step = Step.Working("Sending the detected regions for verification…")
        scope.launch {
            step = when (val r = repo.submit(analysis, route, direction, liveFace = face)) {
                is DocVerifyRepository.Submission.Verified -> Step.Verified(analysis, r.outcome, face)
                is DocVerifyRepository.Submission.Queued -> Step.Queued(analysis, r.localChecks, r.reason)
                is DocVerifyRepository.Submission.Failed -> Step.Failed(r.message)
            }
        }
    }

    fun analyze(bitmap: Bitmap) {
        step = Step.Working("Locating document regions on this phone…")
        scope.launch { step = Step.Review(repo.analyze(bitmap)) }
    }

    // Guided practice (tour): the real screens on a bundled synthetic sample.
    LaunchedEffect(com.pramaanai.officer.ui.tour.VerifyPractice.command) {
        val practice = com.pramaanai.officer.ui.tour.VerifyPractice
        when (practice.command) {
            com.pramaanai.officer.ui.tour.VerifyPractice.Command.LOAD_DOCUMENT -> {
                practice.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.NONE
                analyze(practice.document(context))
            }
            com.pramaanai.officer.ui.tour.VerifyPractice.Command.TO_FACE -> {
                (step as? Step.Review)?.let { step = Step.Face(it.analysis) }
                practice.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.NONE
            }
            com.pramaanai.officer.ui.tour.VerifyPractice.Command.USE_FACE -> {
                val a = (step as? Step.Face)?.analysis ?: (step as? Step.Review)?.analysis
                if (a != null) step = Step.Verified(a, practice.outcome(context), practice.face(context))
                practice.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.NONE
            }
            com.pramaanai.officer.ui.tour.VerifyPractice.Command.FINISH -> {
                step = Step.Capture
                practice.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.NONE
            }
            com.pramaanai.officer.ui.tour.VerifyPractice.Command.NONE -> Unit
        }
    }

    Box(Modifier.fillMaxSize().padding(padding)) {
        when (val s = step) {
            is Step.Capture -> CaptureStep(pending, onImage = ::analyze)
            is Step.Working -> Working(s.message)
            is Step.Review -> ReviewStep(
                analysis = s.analysis, route = route, direction = direction,
                onRoute = { route = it; direction = null }, onDirection = { direction = it },
                onRetake = { step = Step.Capture },
            ) {
                if (com.pramaanai.officer.data.local.AppSettings.askLivePhoto(context)) step = Step.Face(s.analysis)
                else submit(s.analysis, null)
            }
            is Step.Face -> FaceStep(repo, onBack = { step = Step.Review(s.analysis) },
                onSkip = { submit(s.analysis, null) }) { crop -> submit(s.analysis, crop) }
            is Step.Verified -> DocVerifyResultView(s.outcome, s.analysis.bitmap, repo, onNew = { step = Step.Capture }, liveFace = s.face)
            is Step.Queued -> QueuedStep(s, onNew = { step = Step.Capture })
            is Step.Failed -> Column(Modifier.padding(16.dp)) {
                Banner("Could not verify", s.message, DestructiveRed, Icons.Filled.Error)
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Try again", Icons.Filled.Refresh) { step = Step.Capture }
            }
        }
    }
}

// ---------------------------------------------------------------- shared pieces

@Composable
private fun Working(text: String) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator(color = AccentGreen)
        Spacer(Modifier.height(16.dp))
        Text(text, color = MutedForeground)
    }
}

@Composable
private fun PrimaryButton(text: String, icon: ImageVector? = null, modifier: Modifier = Modifier.fillMaxWidth(),
                          enabled: Boolean = true, onClick: () -> Unit) {
    Button(onClick = onClick, enabled = enabled, modifier = modifier.height(56.dp), shape = RoundedCornerShape(10.dp),
        colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark)) {
        icon?.let { Icon(it, contentDescription = null); Spacer(Modifier.width(8.dp)) }
        Text(text, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun Section(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

@Composable
private fun Banner(title: String, body: String, color: Color, icon: ImageVector) {
    Card(colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.12f)),
        border = BorderStroke(1.dp, color.copy(alpha = 0.45f)), shape = RoundedCornerShape(12.dp)) {
        Row(Modifier.fillMaxWidth().padding(16.dp)) {
            Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(30.dp))
            Spacer(Modifier.width(12.dp))
            Column {
                Text(title, color = color, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.height(4.dp))
                Text(body, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun AnnotatedImage(bitmap: Bitmap, boxes: List<Pair<String, List<Float>>>) {
    Box(Modifier.fillMaxWidth().aspectRatio(bitmap.width.toFloat() / bitmap.height)) {
        Image(bitmap.asImageBitmap(), contentDescription = "Captured document", contentScale = ContentScale.FillBounds,
            modifier = Modifier.fillMaxSize())
        Canvas(Modifier.fillMaxSize()) {
            val sx = size.width / bitmap.width
            val sy = size.height / bitmap.height
            boxes.forEach { (label, b) ->
                val c = REGION_COLOURS[label] ?: ChartBlue
                drawRect(c.copy(alpha = 0.12f), topLeft = Offset(b[0] * sx, b[1] * sy), size = Size((b[2] - b[0]) * sx, (b[3] - b[1]) * sy))
                drawRect(c, topLeft = Offset(b[0] * sx, b[1] * sy), size = Size((b[2] - b[0]) * sx, (b[3] - b[1]) * sy),
                    style = Stroke(width = 2.5.dp.toPx()))
            }
        }
    }
}

/** A zoomed crop of one region of the document, the region outlined — so the
 * officer sees exactly where a finding is, not just its name. */
@Composable
private fun RegionThumbnail(img: Bitmap, box: List<Int>, size: androidx.compose.ui.unit.Dp = 96.dp, outline: Boolean = true) {
    val crop = remember(img, box) {
        val w = box[2] - box[0]
        val h = box[3] - box[1]
        val m = (maxOf(w, h) * 0.25f).toInt()
        val l = (box[0] - m).coerceIn(0, img.width - 1)
        val t = (box[1] - m).coerceIn(0, img.height - 1)
        val r = (box[2] + m).coerceIn(l + 1, img.width)
        val b = (box[3] + m).coerceIn(t + 1, img.height)
        Triple(Bitmap.createBitmap(img, l, t, r - l, b - t), l, t)
    }
    val (bmp, ox, oy) = crop
    Box(Modifier.size(size).background(Color.Black, RoundedCornerShape(10.dp))) {
        Image(bmp.asImageBitmap(), contentDescription = "Location of the finding", contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxSize())
        if (outline) Canvas(Modifier.fillMaxSize()) {
            val s = minOf(this.size.width / bmp.width, this.size.height / bmp.height)
            val dx = (this.size.width - bmp.width * s) / 2
            val dy = (this.size.height - bmp.height * s) / 2
            drawRect(DestructiveRed, topLeft = Offset(dx + (box[0] - ox) * s, dy + (box[1] - oy) * s),
                size = Size((box[2] - box[0]) * s, (box[3] - box[1]) * s), style = Stroke(width = 2.dp.toPx()))
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun RegionLegend(counts: Map<String, Int>) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        counts.forEach { (label, n) ->
            Row(Modifier.background(SecondaryDark, RoundedCornerShape(8.dp)).padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(10.dp).background(REGION_COLOURS[label] ?: ChartBlue, CircleShape))
                Spacer(Modifier.width(6.dp))
                Text("$n ${humanize(label)}", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

// ---------------------------------------------------------------- capture

@Composable
private fun CaptureStep(pending: Int, onImage: (Bitmap) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var granted by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted = it }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }?.let(onImage)
    }
    val imageCapture = remember { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY).build() }
    LaunchedEffect(Unit) { if (!granted) permission.launch(Manifest.permission.CAMERA) }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        if (pending > 0) {
            Banner("$pending verification(s) waiting to sync", "Saved encrypted on this phone. They are verified automatically when the connection returns.",
                ChartBlue, Icons.Filled.CloudOff)
            Spacer(Modifier.height(12.dp))
        }
        Text("Place the whole document inside the frame — flat, well lit, no glare.", color = MutedForeground)
        Spacer(Modifier.height(12.dp))
        Box(Modifier.fillMaxWidth().weight(1f).background(Color.Black, RoundedCornerShape(14.dp))
            .tourAnchor("vp_capture_frame")) {
            if (granted) {
                AndroidView(factory = { ctx ->
                    PreviewView(ctx).also { view ->
                        val providerFuture = ProcessCameraProvider.getInstance(ctx)
                        providerFuture.addListener({
                            val provider = providerFuture.get()
                            val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
                            provider.unbindAll()
                            provider.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, imageCapture)
                        }, ContextCompat.getMainExecutor(ctx))
                    }
                }, modifier = Modifier.fillMaxSize())
                // framing guide (ID-1 card proportions)
                Canvas(Modifier.fillMaxSize().padding(24.dp)) {
                    val w = size.width
                    val h = w / 1.586f
                    val top = (size.height - h) / 2
                    drawRoundRect(AccentGreen, topLeft = Offset(0f, top), size = Size(w, h), cornerRadius = CornerRadius(16f),
                        style = Stroke(width = 3.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(28f, 18f))))
                }
            } else {
                Text("Camera permission is needed to capture documents. You can still choose a photo from the gallery.",
                    modifier = Modifier.align(Alignment.Center).padding(24.dp), color = MutedForeground)
            }
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.tourAnchor("vp_capture_buttons")) {
            PrimaryButton("Capture", Icons.Filled.CameraAlt, modifier = Modifier.weight(1f), enabled = granted) {
                imageCapture.takePicture(ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageCapturedCallback() {
                    override fun onCaptureSuccess(image: ImageProxy) {
                        val rotation = image.imageInfo.rotationDegrees
                        val raw = image.toBitmap()
                        image.close()
                        onImage(if (rotation == 0) raw else Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height,
                            Matrix().apply { postRotate(rotation.toFloat()) }, true))
                    }
                    override fun onError(exception: ImageCaptureException) = Unit
                })
            }
            OutlinedButton(
                onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                modifier = Modifier.weight(1f).height(56.dp), shape = RoundedCornerShape(10.dp),
            ) { Icon(Icons.Filled.PhotoLibrary, null); Spacer(Modifier.width(8.dp)); Text("Gallery") }
        }
    }
}

// ---------------------------------------------------------------- review

private val DIRECTIONS = mapOf(
    "INDIA_NEPAL" to listOf("INDIA_TO_NEPAL" to "India → Nepal", "NEPAL_TO_INDIA" to "Nepal → India"),
    "INDIA_BHUTAN" to listOf("INDIA_TO_BHUTAN" to "India → Bhutan", "BHUTAN_TO_INDIA" to "Bhutan → India"),
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ReviewStep(
    analysis: DocVerifyRepository.Analysis,
    route: String?,
    direction: String?,
    onRoute: (String?) -> Unit,
    onDirection: (String?) -> Unit,
    onRetake: () -> Unit,
    onVerify: () -> Unit,
) {
    val chipColors = FilterChipDefaults.filterChipColors(selectedContainerColor = AccentGreen, selectedLabelColor = BackgroundDark)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (!analysis.detectorAvailable) {
            Banner("Region detector unavailable", "The on-phone model could not be loaded. The full image is never uploaded instead.",
                DestructiveRed, Icons.Filled.Error)
        } else if (analysis.detections.none { it.label != "document" }) {
            Banner("No document regions found", "Retake with the whole document in view, flat and without glare.",
                WarningAmber, Icons.Filled.Warning)
        }
        Section("Regions found on this phone", Modifier.tourSection("vp_regions")) {
            AnnotatedImage(analysis.bitmap, analysis.detections.map { it.label to listOf(it.box.left, it.box.top, it.box.right, it.box.bottom) })
            Spacer(Modifier.height(10.dp))
            RegionLegend(analysis.detections.groupingBy { it.label }.eachCount())
            Spacer(Modifier.height(6.dp))
            Text(OnDeviceRegionDetector.NAME, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
        }
        if (analysis.mrzFields.isNotEmpty()) Section("Machine-readable zone (read on this phone)") {
            analysis.mrzFields.forEach { (k, v) -> FieldRow(k, v, null) }
            analysis.localChecks.firstOrNull { it.name.startsWith("MRZ") }?.let {
                Spacer(Modifier.height(6.dp))
                LocalCheckRow(it)
            }
        }
        Section("Text read on this phone (${analysis.text.lines.size} lines)", Modifier.tourSection("vp_text")) {
            var showAll by remember { mutableStateOf(false) }
            if (analysis.text.lines.isEmpty()) Text("No printed text could be read on the phone — the server will read the regions again.",
                color = MutedForeground)
            (if (showAll) analysis.text.lines else analysis.text.lines.take(8)).forEach {
                Text(it.text, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(vertical = 2.dp))
            }
            if (analysis.text.lines.size > 8) Text(if (showAll) "Show less" else "Show all ${analysis.text.lines.size} lines",
                color = AccentGreen, modifier = Modifier.clickable { showAll = !showAll }.padding(vertical = 6.dp))
        }
        Section("Crossing", Modifier.tourSection("vp_crossing")) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(null to "Not specified", "INDIA_NEPAL" to "India–Nepal", "INDIA_BHUTAN" to "India–Bhutan").forEach { (v, l) ->
                    FilterChip(selected = route == v, onClick = { onRoute(v) }, label = { Text(l) }, colors = chipColors)
                }
            }
            DIRECTIONS[route]?.let { options ->
                Spacer(Modifier.height(6.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    options.forEach { (v, l) ->
                        FilterChip(selected = direction == v, onClick = { onDirection(if (direction == v) null else v) },
                            label = { Text(l) }, colors = chipColors)
                    }
                }
            }
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Filled.Lock, contentDescription = null, tint = MutedForeground, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("Only the detected regions and the text read here are sent, in one encrypted request — never the whole photo.",
                color = MutedForeground, style = MaterialTheme.typography.bodySmall)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.tourSection("vp_continue")) {
            OutlinedButton(onClick = onRetake, modifier = Modifier.weight(1f).height(56.dp),
                shape = RoundedCornerShape(10.dp)) { Text("Retake") }
            PrimaryButton("Continue", Icons.AutoMirrored.Filled.ArrowForward, modifier = Modifier.weight(1f),
                enabled = analysis.detectorAvailable, onClick = onVerify)
        }
    }
}

// ---------------------------------------------------------------- live photo

@Composable
private fun FaceStep(repo: DocVerifyRepository, onBack: () -> Unit, onSkip: () -> Unit, onFace: (Bitmap) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    var face by remember { mutableStateOf<Bitmap?>(null) }
    var problem by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var useFront by remember { mutableStateOf(true) }
    val granted = ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
    val imageCapture = remember { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY).build() }
    fun useImage(bmp: Bitmap) {
        busy = true
        scope.launch {
            when (val r = repo.selfieFace(bmp)) {
                is DocVerifyRepository.Selfie.Face -> { face = r.crop; problem = null }
                is DocVerifyRepository.Selfie.Problem -> problem = r.message
            }
            busy = false
        }
    }
    val facePicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        uri ?: return@rememberLauncherForActivityResult
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }?.let(::useImage)
    }

    val current = face
    if (current != null) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("Live photo ready", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Image(current.asImageBitmap(), contentDescription = "Face crop that will be compared", contentScale = ContentScale.Crop,
                modifier = Modifier.size(220.dp).background(Color.Black, RoundedCornerShape(16.dp)))
            Text("Only this face crop is sent. The server compares it with the photo on the document and does not store it.",
                color = MutedForeground, style = MaterialTheme.typography.bodySmall)
            PrimaryButton("Verify document and face", Icons.Filled.DocumentScanner) { onFace(current) }
            OutlinedButton(onClick = { face = null }, modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(10.dp)) {
                Text("Retake live photo")
            }
        }
        return
    }
    if (busy) { Working("Finding the face…"); return }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("Live photo of the traveller", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text("Face the camera at eye level in good light. It is compared with the document photo.",
            color = MutedForeground, style = MaterialTheme.typography.bodyMedium)
        problem?.let { Spacer(Modifier.height(8.dp)); Banner("Retake the live photo", it, WarningAmber, Icons.Filled.Warning) }
        Spacer(Modifier.height(12.dp))
        Box(Modifier.fillMaxWidth().weight(1f).background(Color.Black, RoundedCornerShape(14.dp)).tourAnchor("vp_face_camera")) {
            if (granted) {
                key(useFront) {
                    AndroidView(factory = { ctx ->
                        PreviewView(ctx).also { view ->
                            val providerFuture = ProcessCameraProvider.getInstance(ctx)
                            providerFuture.addListener({
                                val provider = providerFuture.get()
                                val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
                                provider.unbindAll()
                                provider.bindToLifecycle(lifecycleOwner,
                                    if (useFront) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA,
                                    preview, imageCapture)
                            }, ContextCompat.getMainExecutor(ctx))
                        }
                    }, modifier = Modifier.fillMaxSize())
                }
                IconButton(onClick = { useFront = !useFront },
                    modifier = Modifier.align(Alignment.TopEnd).padding(10.dp).background(BackgroundDark.copy(alpha = 0.6f), CircleShape)) {
                    Icon(Icons.Filled.Cameraswitch, contentDescription = if (useFront) "Switch to back camera" else "Switch to front camera",
                        tint = AccentGreen)
                }
                Text(if (useFront) "Front camera" else "Back camera", color = ForegroundLight,
                    style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.align(Alignment.TopStart).padding(14.dp)
                        .background(BackgroundDark.copy(alpha = 0.6f), RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 4.dp))
                Canvas(Modifier.fillMaxSize().padding(32.dp)) {
                    val r = size.minDimension * 0.38f
                    drawOval(AccentGreen, topLeft = Offset(center.x - r * 0.8f, center.y - r), size = Size(r * 1.6f, r * 2f),
                        style = Stroke(width = 3.dp.toPx(), pathEffect = PathEffect.dashPathEffect(floatArrayOf(28f, 18f))))
                }
            } else {
                Text("Camera permission is needed for the live photo. You can skip the face check.",
                    modifier = Modifier.align(Alignment.Center).padding(24.dp), color = MutedForeground)
            }
        }
        Spacer(Modifier.height(12.dp))
        PrimaryButton("Take live photo", Icons.Filled.CameraAlt, enabled = granted) {
            imageCapture.takePicture(ContextCompat.getMainExecutor(context), object : ImageCapture.OnImageCapturedCallback() {
                override fun onCaptureSuccess(image: ImageProxy) {
                    val rotation = image.imageInfo.rotationDegrees
                    val raw = image.toBitmap()
                    image.close()
                    val mirror = useFront
                    useImage(Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height,
                        Matrix().apply { postRotate(rotation.toFloat()); if (mirror) postScale(-1f, 1f) }, true))
                }
                override fun onError(exception: ImageCaptureException) { problem = "The camera could not take the photo — try again" }
            })
        }
        Spacer(Modifier.height(8.dp))
        OutlinedButton(onClick = { facePicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            modifier = Modifier.fillMaxWidth().height(52.dp), shape = RoundedCornerShape(10.dp)) {
            Icon(Icons.Filled.PhotoLibrary, null); Spacer(Modifier.width(8.dp)); Text("Choose from gallery (testing — not a live capture)")
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = onBack, modifier = Modifier.weight(1f).height(52.dp), shape = RoundedCornerShape(10.dp)) { Text("Back") }
            OutlinedButton(onClick = onSkip, modifier = Modifier.weight(1f).height(52.dp), shape = RoundedCornerShape(10.dp)) { Text("Skip face check") }
        }
    }
}

// ---------------------------------------------------------------- result

@Composable
private fun CheckRow(c: CheckDetail, onClick: (() -> Unit)? = null) {
    val ui = statusUi(c.status)
    Row(Modifier.fillMaxWidth().then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier).padding(vertical = 6.dp)) {
        Icon(ui.icon, contentDescription = ui.label, tint = ui.color, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(checkTitle(c.name) + if (!c.blocking) " (advisory)" else "", fontWeight = FontWeight.Medium)
            Text(c.summary, color = MutedForeground, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.width(8.dp))
        Text(ui.label, color = ui.color, style = MaterialTheme.typography.labelSmall)
    }
}

private val CHECK_TITLES = mapOf(
    "ocr" to "Text extraction", "ocr_confidence" to "Reading confidence", "mrz_structure" to "MRZ format",
    "mrz_check_digits" to "MRZ check digits", "mrz_consistency" to "MRZ matches printed details",
    "document_validity" to "Validity dates", "date_logic" to "Date order", "field_format" to "Number format",
    "registry" to "Registry lookup", "registry_consistency" to "Registry details", "photo" to "Document photo",
    "face_verification" to "Face match (live photo)", "secondary_portrait" to "Second portrait",
    "document_face_quality" to "Photo quality", "tampering_analysis" to "Image forensics",
    "stamp_detection" to "Stamps found", "stamp_identification" to "Stamp reading", "stamp_consistency" to "Stamp consistency",
    "stamp_forensics" to "Stamp forensics", "qr_consistency" to "QR matches printed details", "machine_readable_code" to "QR / barcode",
    "digital_signature" to "Digital signature", "device_ocr_agreement" to "Phone vs server reading",
    "image_quality" to "Image quality", "document_type" to "Document type", "visa_requirement" to "Visa requirement",
    "nationality_code" to "Nationality code", "cross_document" to "Across documents", "aadhaar_official" to "Aadhaar official check",
)

internal fun checkTitle(name: String) = CHECK_TITLES[name] ?: humanize(name)

/** Case statuses / admin decisions, worded exactly as on the web console. */
internal fun caseStatusLabel(status: String?): String = when (status) {
    "CLEAR" -> "Cleared"
    "SECONDARY_REVIEW" -> "Re-capture required"
    "HOLD_REFER" -> "Referred for manual review"
    "SENT" -> "Sent to admin"
    "PENDING", "REVIEW_REQUIRED" -> "Awaiting your decision"
    null -> ""
    else -> humanize(status)
}

private val FIELD_ORDER = listOf("name", "surname", "given_names", "document_number", "aadhaar_number", "visa_number",
    "permit_number", "nationality", "sex", "date_of_birth", "place_of_birth", "date_of_issue", "valid_from", "date_of_expiry",
    "issuing_authority", "vehicle_classes", "visa_type", "entries", "duration")

private fun sourceLabel(source: String) = when (source) {
    "mrz" -> "MRZ" to ChartBlue
    "qr", "barcode" -> "QR" to ChartPurple
    "device" -> "Read on phone" to WarningAmber
    "declared" -> "Declared" to MutedForeground
    else -> "Read by server" to SuccessGreen
}

@Composable
internal fun FieldRow(label: String, value: String, source: String?) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, color = MutedForeground, modifier = Modifier.width(128.dp), style = MaterialTheme.typography.bodyMedium)
        Text(value, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
        source?.let {
            val (l, c) = sourceLabel(it)
            Text(l, color = c, style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.border(1.dp, c.copy(alpha = 0.5f), RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 2.dp))
        }
    }
}

@Composable
internal fun LocalCheckRow(c: LocalCheck) {
    val (icon, color) = when (c.passed) {
        true -> Icons.Filled.CheckCircle to SuccessGreen
        false -> Icons.Filled.Warning to WarningAmber
        null -> Icons.Filled.Info to ChartBlue
    }
    Row(Modifier.padding(vertical = 5.dp)) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
        Spacer(Modifier.width(10.dp))
        Text("${c.name}: ${c.detail}")
    }
}

/** The verification result — used right after verifying, and when an
 * officer reopens a verification from Review/History ([bitmap] is then
 * null: the image stays only on the phone that captured it). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DocVerifyResultView(initial: VerificationOutcome, bitmap: Bitmap?, repo: DocVerifyRepository,
                        onNew: (() -> Unit)? = null, liveFace: Bitmap? = null) {
    val scope = rememberCoroutineScope()
    var outcome by remember { mutableStateOf(initial) }
    var docImage by remember { mutableStateOf(bitmap) }
    var faceImage by remember { mutableStateOf(liveFace) }
    LaunchedEffect(initial.id) {
        val id = initial.id ?: return@LaunchedEffect
        if (docImage == null || faceImage == null) {
            val (d, f) = repo.images(id, outcome.case?.screeningVerificationId)
            if (docImage == null) docImage = d
            if (faceImage == null) faceImage = f
        }
    }
    val ui = statusUi(outcome.overallStatus)
    var selectedCheck by remember { mutableStateOf<String?>(null) }
    var showPassed by remember { mutableStateOf(false) }
    val evidenceById = (outcome.evidence ?: emptyList()).associateBy { it.id }
    val relevant = outcome.checkDetails.filter { it.status != "NOT_APPLICABLE" }
    val faceChecks = relevant.filter { it.name == "face_verification" || it.name == "secondary_portrait" }
    val issues = relevant.filter { it.status in setOf("FAIL", "REVIEW_REQUIRED") }
    val pendingOfficial = relevant.filter { it.status !in setOf("FAIL", "REVIEW_REQUIRED", "PASS") }
    val passed = relevant.filter { it.status == "PASS" }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        // ---- headline
        Card(modifier = Modifier.tourSection("vp_result_headline"), colors = CardDefaults.cardColors(containerColor = ui.color.copy(alpha = 0.12f)),
            border = BorderStroke(1.dp, ui.color.copy(alpha = 0.5f)), shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.fillMaxWidth().padding(18.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(ui.icon, contentDescription = null, tint = ui.color, modifier = Modifier.size(34.dp))
                    Spacer(Modifier.width(12.dp))
                    Text(outcome.officerSummary.headline, color = ui.color, fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
                }
                outcome.explanation?.takeIf { it.isNotBlank() }?.let { Spacer(Modifier.height(8.dp)); Text(it) }
                outcome.case?.caseNumber?.let {
                    Spacer(Modifier.height(8.dp))
                    Text("Case $it · ${caseStatusLabel(outcome.case?.status)}", color = MutedForeground,
                        style = MaterialTheme.typography.labelMedium)
                }
                Spacer(Modifier.height(12.dp))
                HorizontalDivider(color = BorderDark)
                Spacer(Modifier.height(12.dp))
                (outcome.officerSummary.facts ?: emptyMap()).forEach { (k, v) ->
                    Row(Modifier.padding(vertical = 2.dp)) {
                        Text(k, color = MutedForeground, modifier = Modifier.width(110.dp))
                        Text(v, fontWeight = FontWeight.Medium)
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text("Risk indicator ${outcome.riskScore}/100 · ${humanize(outcome.riskLevel)} — explained below, never a verdict",
                    color = MutedForeground, style = MaterialTheme.typography.labelMedium)
                LinearProgressIndicator(
                    progress = { outcome.riskScore / 100f },
                    modifier = Modifier.fillMaxWidth().height(8.dp).padding(top = 4.dp),
                    color = if (outcome.riskScore >= 60) DestructiveRed else if (outcome.riskScore >= 25) WarningAmber else SuccessGreen,
                    trackColor = SecondaryDark,
                )
                Text("Evidence completeness ${(outcome.confidence * 100).toInt()}%", color = MutedForeground,
                    style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(top = 6.dp))
            }
        }

        // ---- decision / case
        Box(Modifier.tourSection("vp_decision")) {
            DecisionPanel(outcome, repo) { vid -> if (vid != "practice") scope.launch { repo.load(vid).onSuccess { outcome = it } } }
        }

        // ---- the document, with every problem area marked
        val problemBoxes = issues.flatMap { c -> (c.evidenceIds ?: emptyList()).mapNotNull { evidenceById[it] } }
            .filter { it.bbox != null && (it.documentIndex ?: 0) == 0 }
        docImage?.let { img ->
            Section(if (problemBoxes.isEmpty()) "Document" else "Document — problem areas marked (${problemBoxes.size})",
                Modifier.tourSection("vp_document_problems")) {
                AnnotatedImage(img, problemBoxes.map { "problem" to it.bbox!!.map { v -> v.toFloat() } })
                if (problemBoxes.isEmpty()) Text("No problem area was marked on the document.", color = MutedForeground,
                    style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
            }
        } ?: Section("Document") {
            Text("No document image is stored for this verification — it was captured before images were kept with " +
                "the record. Newer verifications show the document with problem areas marked here.", color = MutedForeground,
                style = MaterialTheme.typography.bodySmall)
        }

        // ---- extracted fields
        outcome.documents.forEach { doc ->
            val fields = doc.fields ?: emptyMap()
            Section("Extracted details — ${humanize(doc.documentType.documentType)}",
                if (doc == outcome.documents.first()) Modifier.tourSection("vp_fields") else Modifier) {
                doc.documentType.country?.let {
                    Text("Country: ${humanize(it)}", color = MutedForeground, style = MaterialTheme.typography.labelMedium)
                    Spacer(Modifier.height(4.dp))
                }
                if (fields.isEmpty()) Text("No printed details could be read.", color = MutedForeground)
                val ordered = FIELD_ORDER.filter { it in fields } + fields.keys.filter { it !in FIELD_ORDER }.sorted()
                ordered.forEach { k -> fields[k]?.let { f -> FieldRow(humanize(k), f.value, f.source) } }
                (doc.stamps ?: emptyList()).forEachIndexed { i, st ->
                    Spacer(Modifier.height(8.dp))
                    Text("Stamp ${i + 1}", fontWeight = FontWeight.SemiBold)
                    listOf("Type" to st.stampType, "Country" to st.country, "Checkpoint" to st.checkpoint,
                        "Direction" to st.direction, "Date" to st.date).forEach { (k, v) ->
                        if (!v.isNullOrBlank()) FieldRow(k, humanize(v), null)
                    }
                }
            }
        }

        // ---- face
        Section("Face match", Modifier.tourSection("vp_face_match")) {
            val photoBox = outcome.checkDetails.filter { it.name == "photo" || it.name == "face_verification" }
                .flatMap { it.evidenceIds ?: emptyList() }.mapNotNull { evidenceById[it]?.bbox }.firstOrNull()
            val img = docImage
            if ((img != null && photoBox != null) || faceImage != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.padding(bottom = 8.dp)) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        if (img != null && photoBox != null) RegionThumbnail(img, photoBox, size = 120.dp, outline = false)
                        else Box(Modifier.size(120.dp).background(SecondaryDark, RoundedCornerShape(10.dp)))
                        Text("Document photo", color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                    }
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        faceImage?.let { f ->
                            Image(f.asImageBitmap(), contentDescription = "Live photo", contentScale = ContentScale.Crop,
                                modifier = Modifier.size(120.dp).background(Color.Black, RoundedCornerShape(10.dp)))
                        } ?: Box(Modifier.size(120.dp).background(SecondaryDark, RoundedCornerShape(10.dp)), contentAlignment = Alignment.Center) {
                            Text("No live photo", color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                        }
                        Text("Live photo", color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
            if (faceChecks.isEmpty()) Text("No live photo was taken, so the face was not compared.", color = MutedForeground)
            faceChecks.forEach { c ->
                CheckRow(c)
                (c.details?.get("similarity_score") as? Number)?.let {
                    Text("Similarity ${"%.2f".format(it.toDouble())} (threshold 0.50)", color = MutedForeground,
                        style = MaterialTheme.typography.labelSmall, modifier = Modifier.padding(start = 30.dp))
                }
            }
        }

        // ---- identity graph
        Box(Modifier.tourSection("vp_identity")) { IdentitySection(outcome) }

        // ---- checks
        if (issues.isNotEmpty()) Section("Needs your attention (${issues.size})", Modifier.tourSection("vp_checks")) {
            issues.forEach { c ->
                CheckRow(c) { selectedCheck = c.name }
                val boxes = (c.evidenceIds ?: emptyList()).mapNotNull { evidenceById[it]?.bbox }.filter { (evidenceById.values.firstOrNull { e -> e.bbox == it }?.documentIndex ?: 0) == 0 }
                val img = docImage
                if (img != null && boxes.isNotEmpty()) Row(Modifier.padding(start = 30.dp, bottom = 8.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    boxes.take(3).forEach { b -> RegionThumbnail(img, b) }
                }
            }
        }
        if (pendingOfficial.isNotEmpty()) Section("Not verified here (${pendingOfficial.size})") {
            pendingOfficial.forEach { c -> CheckRow(c) }
        }
        Section("Passed checks (${passed.size})") {
            Row(Modifier.fillMaxWidth().clickable { showPassed = !showPassed }, verticalAlignment = Alignment.CenterVertically) {
                Text(if (showPassed) "Hide" else "Show all", color = AccentGreen, modifier = Modifier.weight(1f))
                Icon(if (showPassed) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore, contentDescription = null, tint = AccentGreen)
            }
            if (showPassed) passed.forEach { c -> CheckRow(c) }
        }
        outcome.riskBreakdown?.takeIf { it.isNotEmpty() }?.let { parts ->
            Section("What the risk indicator is made of") {
                parts.forEach { p ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                        Text("+${p.points}", color = WarningAmber, fontWeight = FontWeight.Bold, modifier = Modifier.width(44.dp))
                        Column(Modifier.weight(1f)) {
                            Text(checkTitle(p.check), fontWeight = FontWeight.Medium)
                            Text(p.reason, color = MutedForeground, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        }

        // ---- evidence (only on the phone that holds the image)
        docImage?.let { evidenceImage -> Section("View evidence") {
            val chipColors = FilterChipDefaults.filterChipColors(selectedContainerColor = AccentGreen, selectedLabelColor = BackgroundDark)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = selectedCheck == null, onClick = { selectedCheck = null }, label = { Text("All regions") }, colors = chipColors)
                relevant.filter { !it.evidenceIds.isNullOrEmpty() }.map { it.name }.distinct().forEach { name ->
                    FilterChip(selected = selectedCheck == name, onClick = { selectedCheck = name }, label = { Text(checkTitle(name)) }, colors = chipColors)
                }
            }
            Spacer(Modifier.height(8.dp))
            val shownBoxes = outcome.checkDetails
                .filter { selectedCheck == null || it.name == selectedCheck }
                .flatMap { c -> (c.evidenceIds ?: emptyList()).mapNotNull { evidenceById[it] } }
                .filter { it.bbox != null && (it.documentIndex ?: 0) == 0 }
                .map { e ->
                    val kind = when {
                        e.check.startsWith("stamp") -> "stamp"
                        e.check.contains("photo") || e.check.contains("face") || e.check.contains("portrait") -> "photograph"
                        e.check.contains("mrz") -> "mrz"
                        e.check.contains("code") -> "qr_code"
                        e.check.contains("yellow") -> "yellow_gold_feature"
                        else -> "document"
                    }
                    kind to e.bbox!!.map { it.toFloat() }
                }
            AnnotatedImage(evidenceImage, shownBoxes)
            selectedCheck?.let { name -> relevant.filter { it.name == name }.forEach { CheckRow(it) } }
        } }

        outcome.officerSummary.responsibilityNotice?.let { Text(it, color = MutedForeground, style = MaterialTheme.typography.bodySmall) }
        outcome.dataNotice?.let { Text(it, color = MutedForeground, style = MaterialTheme.typography.bodySmall) }
        onNew?.let { PrimaryButton("Verify another document", Icons.Filled.DocumentScanner, onClick = it) }
    }
}

@Composable
private fun IdentitySection(outcome: VerificationOutcome) {
    val identity = outcome.identity
    Section("Identity graph") {
        if (identity == null) {
            Text("Not built for this verification (no case was opened).", color = MutedForeground)
            return@Section
        }
        val cluster = identity.faceCluster
        val fields = outcome.documents.firstOrNull()?.fields ?: emptyMap()
        val selfNode = com.pramaanai.officer.data.model.IdentityClusterMember(
            recordId = "this-traveller", referenceName = fields["name"]?.value ?: "This traveller",
            documentNumber = (fields["document_number"] ?: fields["visa_number"] ?: fields["permit_number"])?.value,
            relationshipType = "THIS_SCREENING")
        val linked = (cluster?.members ?: emptyList())
            .filter { it.referenceName != selfNode.referenceName || it.documentNumber != selfNode.documentNumber }
            .map {
                com.pramaanai.officer.data.model.IdentityClusterMember(
                    recordId = it.recordId ?: "", referenceName = it.referenceName ?: "Unknown",
                    documentNumber = it.documentNumber, relationshipType = "SIMILAR_IDENTITY")
            }
        com.pramaanai.officer.ui.components.IdentityClusterGraph(members = listOf(selfNode) + linked)
        Spacer(Modifier.height(8.dp))
        when {
            cluster == null -> {}
            cluster.status == "CLUSTER_FOUND" -> {
                Banner("Same face under a different identity", (cluster.reason ?: "") +
                    " — compare the records before deciding.", WarningAmber, Icons.Filled.Warning)
            }
            else -> Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = SuccessGreen, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(10.dp))
                Text("No earlier screening shows this face under another name or document number.")
            }
        }
        identity.duplicateDocument?.let { d ->
            Spacer(Modifier.height(8.dp))
            val (icon, color, text) = when (d.status) {
                "NO_MATCH" -> Triple(Icons.Filled.CheckCircle, SuccessGreen, "Document number not seen on other cases.")
                "SAME_IDENTITY_REUSE" -> Triple(Icons.Filled.Info, ChartBlue, "Seen before with the same identity (${d.matchCount}×) — a repeat traveller.")
                else -> Triple(Icons.Filled.Warning, WarningAmber, d.reason ?: "Document number seen under a different name.")
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(10.dp))
                Text(text)
            }
        }
        identity.notes?.forEach { Text(it, color = MutedForeground, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp)) }
    }
}

@Composable
private fun DecisionPanel(outcome: VerificationOutcome, repo: DocVerifyRepository, onChanged: (String) -> Unit) {
    val scope = rememberCoroutineScope()
    val vid = outcome.id ?: return
    val case = outcome.case
    val status = case?.status
    val suggestions = outcome.suggestedReasons ?: emptyMap()
    var mode by remember { mutableStateOf<String?>(null) }  // "clear" | "send"
    var reason by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    when (status) {
        "SENT" -> { Section("Sent to admin") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null, tint = ChartBlue)
                Spacer(Modifier.width(10.dp))
                Text("Waiting for the admin's response on the web console. It appears here and in Review.")
            }
            case.notes?.lastOrNull()?.let { Spacer(Modifier.height(8.dp)); Text("Your note: ${it.note}", color = MutedForeground) }
            TextButton(onClick = { onChanged(vid) }) { Text("Check for a response", color = AccentGreen) }
        }; return }
        "CLEAR", "SECONDARY_REVIEW", "HOLD_REFER" -> { Section("Decision") {
            case.decisions?.forEach { d ->
                val byReviewer = d.role == "REVIEWER"
                Text(if (byReviewer) "Admin's response" else "Your decision", fontWeight = FontWeight.SemiBold)
                Text("${caseStatusLabel(d.decision)} · ${d.username ?: ""}", color = if (d.decision == "CLEAR") SuccessGreen else WarningAmber,
                    fontWeight = FontWeight.Bold)
                d.reason?.let { Text(it) }
                Spacer(Modifier.height(8.dp))
            }
            case.notes?.filter { it.role == "REVIEWER" }?.forEach { n ->
                Text("Note from ${n.username}: ${n.note}", color = MutedForeground)
            }
        }; return }
    }

    Section("Your decision") {
        Text("The system does not decide. Choose, and check the reason written for you.", color = MutedForeground,
            style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            listOf("clear" to "Clear", "send" to "Send to admin").forEach { (m, label) ->
                val selected = mode == m
                val color = if (m == "clear") SuccessGreen else ChartBlue
                OutlinedButton(
                    onClick = { mode = m; reason = suggestions[m] ?: ""; message = null },
                    modifier = Modifier.weight(1f).height(56.dp), shape = RoundedCornerShape(10.dp),
                    border = BorderStroke(if (selected) 2.dp else 1.dp, if (selected) color else BorderDark),
                    colors = ButtonDefaults.outlinedButtonColors(containerColor = if (selected) color.copy(alpha = 0.15f) else Color.Transparent),
                ) {
                    Icon(if (m == "clear") Icons.Filled.CheckCircle else Icons.AutoMirrored.Filled.Send, null, tint = color)
                    Spacer(Modifier.width(8.dp))
                    Text(label, color = color, fontWeight = FontWeight.SemiBold)
                }
            }
        }
        mode?.let { m ->
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(value = reason, onValueChange = { reason = it },
                label = { Text(if (m == "clear") "Reason (written automatically — edit if needed)" else "Message to the admin") },
                modifier = Modifier.fillMaxWidth(), minLines = 3)
            Spacer(Modifier.height(8.dp))
            PrimaryButton(if (m == "clear") "Confirm clear" else "Send to admin",
                if (m == "clear") Icons.Filled.CheckCircle else Icons.AutoMirrored.Filled.Send,
                enabled = !busy && (m == "clear" && outcome.overallStatus == "PASS" || reason.isNotBlank())) {
                if (vid == "practice") {
                    message = "Practice mode — nothing was sent. In a real verification this " +
                        (if (m == "clear") "records your clearance in the audit trail." else "sends the case, the document image and the live photo to the admin.")
                    return@PrimaryButton
                }
                busy = true
                scope.launch {
                    val action = if (m == "clear") "CLEARED" else "SEND_TO_OFFICER"
                    val evidence = if (m == "send") repo.uploadEvidence(outcome).fold(
                        { n -> if (n == 2) "Document image and live photo attached for the admin. " else "Document image attached for the admin. " },
                        { "Images could not be attached (${it.message}); the case is sent with its findings. " }) else ""
                    message = evidence + repo.recordAction(vid, action, reason.ifBlank { null }).fold(
                        { if (m == "clear") "Cleared — recorded in the audit trail." else "Sent — the admin's response will appear here." },
                        { "Could not record the decision — check the connection and try again." })
                    busy = false
                    onChanged(vid)
                }
            }
        }
        if (case?.caseNumber == null) {
            Spacer(Modifier.height(6.dp))
            Text(case?.reason?.let { "No case was opened: $it" } ?: "No case was opened for this verification.",
                color = MutedForeground, style = MaterialTheme.typography.bodySmall)
        }
        message?.let { Text(it, color = MutedForeground, modifier = Modifier.padding(top = 8.dp)) }
    }
}

// ---------------------------------------------------------------- offline

@Composable
private fun QueuedStep(s: Step.Queued, onNew: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Banner("OFFLINE VERIFICATION", "${s.reason}. External registry verification unavailable. The regions are saved encrypted on this " +
            "phone and will be verified by the server automatically when the connection returns.", ChartBlue, Icons.Filled.CloudOff)
        Section("Regions found on this phone") {
            AnnotatedImage(s.analysis.bitmap, s.analysis.detections.map { it.label to listOf(it.box.left, it.box.top, it.box.right, it.box.bottom) })
        }
        Section("Checked on this phone") {
            s.checks.forEach { LocalCheckRow(it) }
            LocalCheckRow(LocalCheck("Registry, server OCR and image forensics", null, "pending — not checked while offline"))
        }
        PrimaryButton("Verify another document", Icons.Filled.DocumentScanner, onClick = onNew)
    }
}
