# App classes are kept whole: Gson maps JSON onto them by reflection and
# Retrofit reads the API interfaces' annotations.
-keep class com.pramaanai.officer.** { *; }
-keepattributes Signature, InnerClasses, EnclosingMethod, *Annotation*, RuntimeVisibleAnnotations, RuntimeVisibleParameterAnnotations

# Retrofit / OkHttp / Gson
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation
-keep class com.google.gson.reflect.TypeToken { *; }
-keep class * extends com.google.gson.reflect.TypeToken
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn javax.annotation.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# ONNX Runtime uses JNI back into these classes
-keep class ai.onnxruntime.** { *; }

# WorkManager instantiates workers reflectively
-keep class * extends androidx.work.ListenableWorker { <init>(...); }

# ML Kit (text, barcode, face) — its internals are wired up reflectively
# through component registrars; shrinking them crashed text recognition on a
# real device (NullPointerException inside ML Kit) in the minified build.
-keep class com.google.mlkit.** { *; }
-keep class com.google.android.gms.internal.mlkit_** { *; }
-keep class com.google.android.gms.vision.** { *; }
-keep class com.google.firebase.components.** { *; }
-keep class * implements com.google.firebase.components.ComponentRegistrar { *; }
-dontwarn com.google.mlkit.**
-dontwarn com.google.android.gms.internal.mlkit_**
