package com.bordershield.officer.ui.capture

import android.Manifest
import android.content.pm.PackageManager
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.ui.components.WorkflowStepper
import kotlinx.coroutines.launch
import java.io.File
import java.io.FileOutputStream
import kotlin.random.Random

private val LIVENESS_PROMPTS = listOf(
    "Turn your head slowly to the left",
    "Turn your head slowly to the right",
    "Blink twice",
    "Nod your head once",
    "Look directly at the camera and hold still",
)

private enum class CaptureStep { DOCUMENT, SELFIE, SUBMITTING, ERROR }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CaptureScreen(
    repository: ScreeningRepository,
    travelerName: String,
    documentType: String,
    nationality: String,
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
    }

    var step by remember { mutableStateOf(CaptureStep.DOCUMENT) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var documentFile by remember { mutableStateOf<File?>(null) }
    var selfieFile by remember { mutableStateOf<File?>(null) }
    val livenessPrompt = remember(step) { LIVENESS_PROMPTS[Random.nextInt(LIVENESS_PROMPTS.size)] }

    fun submit() {
        val front = documentFile ?: return
        step = CaptureStep.SUBMITTING
        scope.launch {
            try {
                val item = repository.submitScreening(
                    travelerName = travelerName,
                    documentType = documentType,
                    nationality = nationality,
                    frontImageFile = front,
                    liveImageFile = selfieFile,
                )
                onSubmitted(item.id)
            } catch (e: Exception) {
                errorMessage = e.message ?: e.toString()
                step = CaptureStep.ERROR
            }
        }
    }

    fun onImageReady(outputFile: File, label: String) {
        Toast.makeText(context, "Using: $label", Toast.LENGTH_SHORT).show()
        if (step == CaptureStep.DOCUMENT) {
            documentFile = outputFile
            step = CaptureStep.SELFIE
        } else {
            selfieFile = outputFile
            submit()
        }
    }

    // Testing convenience, not part of the real checkpoint workflow: pick an
    // existing photo instead of using the live camera, so front-document and
    // selfie images can be swapped in without needing a physical document or
    // a second person in frame. Copies the picked content:// URI's bytes to
    // the same cache file the camera path writes, so downstream code (and
    // the real POST /documents/screen upload) can't tell the difference.
    val pickMediaLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        val fileName = if (step == CaptureStep.DOCUMENT) "document_photo.jpg" else "live_selfie.jpg"
        val outputFile = File(context.cacheDir, fileName)
        try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(outputFile).use { output -> input.copyTo(output) }
            }
            onImageReady(outputFile, "uploaded photo")
        } catch (e: Exception) {
            Toast.makeText(context, "Upload failed: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    Scaffold(topBar = { TopAppBar(title = { Text("Capture") }) }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (step != CaptureStep.SUBMITTING && step != CaptureStep.ERROR) {
                WorkflowStepper(currentStep = 1, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(12.dp))
            }
            if (!hasCameraPermission) {
                Text("Camera permission is required to capture documents and a live selfie.")
                Spacer(Modifier.height(12.dp))
                Button(onClick = { permissionLauncher.launch(Manifest.permission.CAMERA) }) {
                    Text("Grant camera permission")
                }
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
                OutlinedButton(onClick = { step = CaptureStep.DOCUMENT }) { Text("Start over") }
                return@Column
            }

            when (step) {
                CaptureStep.DOCUMENT -> {
                    Text("Step 1 of 2 — Document photo", style = MaterialTheme.typography.titleMedium)
                    Text("Position the passport/ID inside the frame", style = MaterialTheme.typography.bodyMedium)
                }
                CaptureStep.SELFIE -> {
                    Text("Step 2 of 2 — Live selfie", style = MaterialTheme.typography.titleMedium)
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

            CameraPreview(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
                lensFacing = if (step == CaptureStep.DOCUMENT) CameraSelector.LENS_FACING_BACK else CameraSelector.LENS_FACING_FRONT,
                onImageCaptureReady = { imageCapture = it },
            )

            Spacer(Modifier.height(12.dp))

            Button(
                onClick = {
                    val capture = imageCapture ?: return@Button
                    val fileName = if (step == CaptureStep.DOCUMENT) "document_photo.jpg" else "live_selfie.jpg"
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
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (step == CaptureStep.DOCUMENT) "Capture document photo" else "Capture selfie")
            }

            Spacer(Modifier.height(8.dp))

            OutlinedButton(
                onClick = {
                    pickMediaLauncher.launch(
                        PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                    )
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Or upload a photo instead (testing)")
            }
        }
    }
}

@Composable
private fun CameraPreview(
    modifier: Modifier = Modifier,
    lensFacing: Int,
    onImageCaptureReady: (ImageCapture) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    AndroidView(
        modifier = modifier,
        factory = { ctx -> PreviewView(ctx) },
        update = { previewView ->
            val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()
                val preview = Preview.Builder().build().also {
                    it.surfaceProvider = previewView.surfaceProvider
                }
                val capture = ImageCapture.Builder().build()
                val selector = CameraSelector.Builder().requireLensFacing(lensFacing).build()
                try {
                    cameraProvider.unbindAll()
                    cameraProvider.bindToLifecycle(lifecycleOwner, selector, preview, capture)
                    onImageCaptureReady(capture)
                } catch (_: Exception) {
                    // No camera matching this lens facing on the current
                    // device/emulator config — preview just won't render;
                    // the capture flow's button will no-op rather than crash.
                }
            }, ContextCompat.getMainExecutor(context))
        },
    )
}
