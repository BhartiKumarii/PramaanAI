package com.bordershield.officer.data.remote

import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/** Holds the officer's bearer token in memory for the life of the process.
 * Phase 3 simplification: the app auto-logs-in with a fixed dev officer
 * account on startup (see MainActivity) rather than showing a login screen —
 * a real deployment needs one, this is a hackathon-scope stand-in. */
object AuthSession {
    @Volatile
    var accessToken: String? = null

    @Volatile
    var username: String? = null

    @Volatile
    var role: String? = null

    @Volatile
    var loginAt: Long? = null

    fun bearerHeader(): String = "Bearer ${accessToken ?: error("Not logged in")}"

    fun isLoggedIn(): Boolean = accessToken != null

    fun clear() {
        accessToken = null
        username = null
        role = null
        loginAt = null
    }
}

object RetrofitClient {
    // Local dev backend (docker compose). Requires `adb reverse tcp:8000
    // tcp:8000` against whichever device this is installed on (emulator or
    // a real phone over USB) — that forwards the device's own port 8000
    // back to this host's port 8000. Works identically on both, unlike the
    // emulator-only 10.0.2.2 alias. Use this while actively changing
    // backend code — it's instant, no deploy round-trip.
    private const val LOCAL_BASE_URL = "http://127.0.0.1:8000/"

    // Render deployment (see /render.yaml) — real HTTPS, no USB tether or
    // adb tunnel needed, works over WiFi/mobile data. Free-tier service
    // sleeps after ~15 min idle, so the first request after a gap can take
    // 30-50s to wake it up. Swap BASE_URL below to switch.
    private const val RENDER_BASE_URL = "https://bordershield-pramaan-api.onrender.com/"

    private const val BASE_URL = RENDER_BASE_URL

    private val gson = GsonBuilder()
        .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
        .create()

    val apiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(OkHttpClient.Builder().build())
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }
}
