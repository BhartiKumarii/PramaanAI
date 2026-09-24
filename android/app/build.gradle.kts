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
        versionCode = 5
        versionName = "1.3.1"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Backend URL. Default: the Render deployment. For a local test build
        // pass -Ppramaan.apiUrl=http://127.0.0.1:8000/ (with `adb reverse
        // tcp:8000 tcp:8000`) or the laptop's LAN address.
        val apiUrl = (project.findProperty("pramaan.apiUrl") as String?)
            ?: "https://bordershield-pramaan-api.onrender.com/"
        buildConfigField("String", "API_BASE_URL", "\"$apiUrl\"")
        // Phones are ARM; the x86 libraries (ONNX Runtime, ML Kit) only serve
        // emulators and roughly double the APK. -Ppramaan.emulatorAbis=true
        // adds them back for emulator testing.
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a")
            if (project.findProperty("pramaan.emulatorAbis") == "true") {
                abiFilters += listOf("x86", "x86_64")
            }
        }
    }

    buildTypes {
        release {
            // R8 removes unused library code; the app's own classes are kept
            // whole (Gson/Retrofit read them by reflection) — proguard-rules.pro.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Demo/test builds are signed with the local debug key so they
            // install directly; a production release needs its own keystore.
            signingConfig = signingConfigs.getByName("debug")
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
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")

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
    // On-device YOLO11n region detector (document / photo / MRZ / QR / stamp /
    // yellow-gold feature), exported to ONNX from scripts/docverify/yolo.
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.20.0")

    testImplementation("junit:junit:4.13.2")

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
