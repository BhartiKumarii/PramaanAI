package com.pramaanai.officer.ui.capture

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.pramaanai.officer.R
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlinx.coroutines.launch
import java.io.File

/**
 * Enhanced Capture Screen with Controlled Auto-Capture
 *
 * Features:
 * 1. Manual capture mode (default)
 * 2. Optional auto-capture with user control
 * 3. Professional UI with clear feedback
 * 4. Multi-language support
 * 5. Document quality assessment
 */

enum class CaptureMode {
    MANUAL,           // User taps to capture (default)
    AUTO_ASSISTED,    // Shows when ready, user confirms
    AUTO_CAPTURE      // Captures automatically when quality is good
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EnhancedCaptureScreen(
    onImageCaptured: (File, String) -> Unit,
    onBack: () -> Unit
) {
    var captureMode by remember { mutableStateOf(CaptureMode.MANUAL) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var isReady by remember { mutableStateOf(false) }
    var qualityScore by remember { mutableStateOf(0f) }
    var statusMessage by remember { mutableStateOf("Position document in frame") }

    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    // Permission handling
    val hasCameraPermission = ContextCompat.checkSelfPermission(
        context, Manifest.permission.CAMERA
    ) == PackageManager.PERMISSION_GRANTED

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(context, "Camera permission required", Toast.LENGTH_SHORT).show()
        }
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) {
            permissionLauncher.launch(Manifest.permission.CAMERA)
        }
    }

    // Auto-capture handler
    LaunchedEffect(captureMode, isReady, qualityScore) {
        if (captureMode == CaptureMode.AUTO_CAPTURE && isReady && qualityScore > 0.8f) {
            // Wait a moment for stability, then auto-capture
            kotlinx.coroutines.delay(1000)
            if (isReady && qualityScore > 0.8f) {
                captureImage(imageCapture, context, onImageCaptured)
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Document Capture") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    // Capture mode toggle
                    IconButton(
                        onClick = {
                            captureMode = when (captureMode) {
                                CaptureMode.MANUAL -> CaptureMode.AUTO_ASSISTED
                                CaptureMode.AUTO_ASSISTED -> CaptureMode.AUTO_CAPTURE
                                CaptureMode.AUTO_CAPTURE -> CaptureMode.MANUAL
                            }
                        }
                    ) {
                        Icon(
                            when (captureMode) {
                                CaptureMode.MANUAL -> Icons.Default.TouchApp
                                CaptureMode.AUTO_ASSISTED -> Icons.Default.AssistantPhoto
                                CaptureMode.AUTO_CAPTURE -> Icons.Default.AutoAwesome
                            },
                            contentDescription = "Capture Mode"
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // Capture mode indicator
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = when (captureMode) {
                        CaptureMode.MANUAL -> MaterialTheme.colorScheme.surfaceVariant
                        CaptureMode.AUTO_ASSISTED -> MaterialTheme.colorScheme.primaryContainer
                        CaptureMode.AUTO_CAPTURE -> MaterialTheme.colorScheme.tertiaryContainer
                    }
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        when (captureMode) {
                            CaptureMode.MANUAL -> Icons.Default.TouchApp
                            CaptureMode.AUTO_ASSISTED -> Icons.Default.AssistantPhoto
                            CaptureMode.AUTO_CAPTURE -> Icons.Default.AutoAwesome
                        },
                        contentDescription = null,
                        modifier = Modifier.size(24.dp)
                    )
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = when (captureMode) {
                                CaptureMode.MANUAL -> "Manual Capture"
                                CaptureMode.AUTO_ASSISTED -> "Auto-Assisted"
                                CaptureMode.AUTO_CAPTURE -> "Auto-Capture"
                            },
                            fontWeight = FontWeight.Medium
                        )
                        Text(
                            text = when (captureMode) {
                                CaptureMode.MANUAL -> "Tap button to capture"
                                CaptureMode.AUTO_ASSISTED -> "Shows when ready to capture"
                                CaptureMode.AUTO_CAPTURE -> "Captures automatically when ready"
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Camera preview
            if (hasCameraPermission) {
                EnhancedCameraPreviewFixed(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    onImageCaptureReady = { imageCapture = it },
                    onQualityChanged = { quality, ready, message ->
                        qualityScore = quality
                        isReady = ready
                        statusMessage = message
                    },
                    captureMode = captureMode
                )
            } else {
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center
                    ) {
                        Icon(
                            Icons.Default.CameraAlt,
                            contentDescription = null,
                            modifier = Modifier.size(64.dp),
                            tint = MaterialTheme.colorScheme.onErrorContainer
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Text(
                            "Camera Permission Required",
                            style = MaterialTheme.typography.headlineSmall,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            "Grant camera permission to capture documents",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                        Spacer(modifier = Modifier.height(24.dp))
                        Button(
                            onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }
                        ) {
                            Text("Grant Permission")
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Status and quality indicator
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp)
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            statusMessage,
                            style = MaterialTheme.typography.bodyMedium
                        )

                        // Quality indicator
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Icon(
                                if (isReady) Icons.Default.CheckCircle else Icons.Default.Info,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = if (isReady) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Spacer(modifier = Modifier.width(4.dp))
                            Text(
                                "${(qualityScore * 100).toInt()}%",
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isReady) AccentGreen else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    // Quality bar
                    Spacer(modifier = Modifier.height(8.dp))
                    LinearProgressIndicator(
                        progress = qualityScore,
                        modifier = Modifier.fillMaxWidth(),
                        color = if (isReady) AccentGreen else MaterialTheme.colorScheme.primary
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Capture button (only for manual and auto-assisted modes)
            if (captureMode != CaptureMode.AUTO_CAPTURE) {
                Button(
                    onClick = {
                        captureImage(imageCapture, context, onImageCaptured)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    enabled = if (captureMode == CaptureMode.AUTO_ASSISTED) isReady else true,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = AccentGreen,
                        contentColor = BackgroundDark,
                        disabledContainerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Row(
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Icon(
                            Icons.Default.PhotoCamera,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            if (captureMode == CaptureMode.AUTO_ASSISTED && !isReady)
                                "Waiting for Good Quality..."
                            else
                                "Capture Document",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }
            } else {
                // Auto-capture mode - show status
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer
                    )
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.Center,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (isReady) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                "Auto-capturing in 1 second...",
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                        } else {
                            Icon(
                                Icons.Default.AutoAwesome,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                                tint = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                            Spacer(modifier = Modifier.width(12.dp))
                            Text(
                                "Auto-capture ready - improve document position",
                                color = MaterialTheme.colorScheme.onTertiaryContainer
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun EnhancedCameraPreviewFixed(
    modifier: Modifier = Modifier,
    onImageCaptureReady: (ImageCapture) -> Unit,
    onQualityChanged: (quality: Float, isReady: Boolean, message: String) -> Unit,
    captureMode: CaptureMode
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    AndroidView(
        modifier = modifier.clip(RoundedCornerShape(12.dp)),
        factory = { ctx ->
            PreviewView(ctx).apply {
                implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            }
        },
        update = { previewView ->
            val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()

                val preview = Preview.Builder()
                    .build()
                    .also { it.surfaceProvider = previewView.surfaceProvider }

                val imageCapture = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MAXIMIZE_QUALITY)
                    .build()

                // Quality analysis
                val imageAnalysis = ImageAnalysis.Builder()
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setTargetResolution(android.util.Size(640, 480))
                    .build()
                    .also { analysis ->
                        analysis.setAnalyzer(ContextCompat.getMainExecutor(context)) { imageProxy ->
                            // Controlled quality analysis - NO AUTO CAPTURE HERE
                            analyzeQualityOnly(imageProxy, onQualityChanged)
                        }
                    }

                val cameraSelector = CameraSelector.Builder()
                    .requireLensFacing(CameraSelector.LENS_FACING_BACK)
                    .build()

                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        cameraSelector,
                        preview,
                        imageCapture,
                        imageAnalysis
                    )
                    onImageCaptureReady(imageCapture)
                } catch (e: Exception) {
                    Log.e("CameraPreview", "Camera bind failed", e)
                    onQualityChanged(0f, false, "Camera initialization failed")
                }
            }, ContextCompat.getMainExecutor(context))
        }
    )
}

private fun analyzeQualityOnly(
    imageProxy: ImageProxy,
    onQualityChanged: (quality: Float, isReady: Boolean, message: String) -> Unit
) {
    try {
        val mediaImage = imageProxy.image
        if (mediaImage != null) {
            // Simple quality analysis based on image sharpness and brightness
            val buffer = mediaImage.planes[0].buffer
            val data = ByteArray(buffer.remaining())
            buffer.get(data)

            // Calculate basic quality metrics
            val brightness = calculateBrightness(data)
            val sharpness = calculateSharpness(data, mediaImage.width, mediaImage.height)

            // Combine metrics for overall quality
            val quality = combineQualityMetrics(brightness, sharpness)
            val isReady = quality > 0.7f

            val message = when {
                quality < 0.3f -> "Poor quality - improve lighting and focus"
                quality < 0.7f -> "Fair quality - move closer or improve lighting"
                else -> "Good quality - ready to capture"
            }

            onQualityChanged(quality, isReady, message)
        } else {
            onQualityChanged(0f, false, "Camera error")
        }
    } catch (e: Exception) {
        onQualityChanged(0f, false, "Analysis error: ${e.message}")
    } finally {
        imageProxy.close()
    }
}

private fun calculateBrightness(data: ByteArray): Float {
    var sum = 0L
    for (byte in data) {
        sum += byte.toUByte().toInt()
    }
    return (sum / data.size.toFloat()) / 255f
}

private fun calculateSharpness(data: ByteArray, width: Int, height: Int): Float {
    // Simplified Laplacian variance for sharpness
    if (data.size < width * height) return 0f

    var variance = 0f
    val centerStart = (height / 4) * width + (width / 4)
    val centerEnd = centerStart + (width / 2)

    try {
        for (i in centerStart until minOf(centerEnd, data.size - width - 1)) {
            if (i % width > width - 2) continue

            val center = data[i].toInt() and 0xFF
            val right = data[i + 1].toInt() and 0xFF
            val bottom = data[i + width].toInt() and 0xFF

            val grad = kotlin.math.abs(right - center) + kotlin.math.abs(bottom - center)
            variance += grad * grad
        }

        val pixelCount = kotlin.math.min(centerEnd - centerStart, data.size / 4)
        return if (pixelCount > 0) kotlin.math.sqrt(variance / pixelCount) / 255f else 0f
    } catch (e: Exception) {
        return 0f
    }
}

private fun combineQualityMetrics(brightness: Float, sharpness: Float): Float {
    // Ideal brightness is around 0.4-0.7
    val brightnessScore = 1f - kotlin.math.abs(brightness - 0.55f) / 0.55f
    val brightnessWeight = kotlin.math.max(0f, brightnessScore)

    // Sharpness should be as high as possible
    val sharpnessWeight = kotlin.math.min(1f, sharpness * 3f)

    // Combine with weights
    return (brightnessWeight * 0.4f + sharpnessWeight * 0.6f)
}

private fun captureImage(
    imageCapture: ImageCapture?,
    context: android.content.Context,
    onImageCaptured: (File, String) -> Unit
) {
    val capture = imageCapture ?: return

    val outputFile = File(context.cacheDir, "captured_document_${System.currentTimeMillis()}.jpg")
    val outputOptions = ImageCapture.OutputFileOptions.Builder(outputFile).build()

    capture.takePicture(
        outputOptions,
        ContextCompat.getMainExecutor(context),
        object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                onImageCaptured(outputFile, "Document captured successfully")
            }

            override fun onError(exception: ImageCaptureException) {
                Toast.makeText(context, "Capture failed: ${exception.message}", Toast.LENGTH_SHORT).show()
            }
        }
    )
}