plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.pramaanai.officer"
    compileSdk = 37
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "com.pramaanai.officer"
        minSdk = 26
        targetSdk = 37
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.02.01")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.10.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.4")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.4")
    implementation("androidx.activity:activity-compose:1.8.0")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.material:material-icons-extended")

    implementation("androidx.navigation:navigation-compose:2.8.2")

    // CameraX
    val cameraxVersion = "1.4.0"
    implementation("androidx.camera:camera-core:$cameraxVersion")
    implementation("androidx.camera:camera-camera2:$cameraxVersion")
    implementation("androidx.camera:camera-lifecycle:$cameraxVersion")
    implementation("androidx.camera:camera-view:$cameraxVersion")
    implementation("androidx.camera:camera-mlkit-vision:$cameraxVersion")

    // Local cache of recent screenings: a Gson+file-backed store, not Room —
    // see LocalScreeningStore.kt for why (AGP 9.x's built-in-Kotlin + KSP2
    // combination hits an unresolved upstream bug processing Room's
    // annotations; a plain JSON-file store needs no annotation processor).
    implementation("com.google.code.gson:gson:2.11.0")

    // Retrofit — Phase 3 points this at the real FastAPI backend
    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    // On-device OCR (document fields + MRZ zone text) — real Google Play
    // Services text recognizer, runs entirely on-device, no network call,
    // no server ever sees the image (see app/schemas/verification.py's
    // ScreeningSubmission on the backend: only extracted text/vectors
    // cross the wire).
    implementation("com.google.mlkit:text-recognition:16.0.1")
    implementation("com.google.mlkit:text-recognition-devanagari:16.0.1")

    // On-device face detection (presence/count/position over the live
    // selfie capture) — real Google Play Services detector, same
    // on-device/no-network posture as text-recognition above; only the
    // structured FaceDetectionResult crosses the wire, never the image
    // (see FaceDetectionAnalyzer.kt and the backend's
    // app/services/face/base.py FaceDetectionResult).
    implementation("com.google.mlkit:face-detection:16.1.7")

    // On-device barcode/QR scanning for documents that embed machine-readable
    // codes (e.g., Aadhaar QR, e-Visa barcodes). Decoded content is compared
    // against OCR-extracted fields as an independent verification signal.
    implementation("com.google.mlkit:barcode-scanning:17.3.0")

    // Offline submission queue. Plain WorkManager (no Room integration)
    // needs no annotation processor, so it doesn't hit the same AGP
    // 9.x + KSP2 bug that ruled out Room for LocalScreeningStore.
    implementation("androidx.work:work-runtime-ktx:2.11.2")

    // TFLite runtime — runs MobileFaceNet and anti-spoof models on-device.
    // Model files go in assets/models/; NeuralFaceEmbedding.kt and
    // AntiSpoofDetector.kt handle "model not found" gracefully.
    implementation("org.tensorflow:tensorflow-lite:2.16.1")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
