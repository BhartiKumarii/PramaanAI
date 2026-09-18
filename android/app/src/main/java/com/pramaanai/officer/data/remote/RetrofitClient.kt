package com.pramaanai.officer.data.remote

import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import com.pramaanai.officer.data.local.PersistedSession
import com.pramaanai.officer.data.local.SessionStore
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.io.IOException
import java.util.concurrent.TimeUnit

/** Holds the officer's bearer token and identity in memory for the life of
 * the process — populated by [com.pramaanai.officer.data.ScreeningRepository.login]
 * from the real /auth/login + /auth/me responses, never client-chosen. */
object AuthSession {
    @Volatile
    var accessToken: String? = null

    // Kept (not discarded after login) so the access token — which the
    // backend expires after 30 minutes — can be renewed without asking the
    // officer to sign in again. See [TokenAuthenticator].
    @Volatile
    var refreshToken: String? = null

    @Volatile
    var username: String? = null

    @Volatile
    var role: String? = null

    @Volatile
    var loginAt: Long? = null

    // Server-authoritative checkpoint assignment (see /auth/me) — null
    // until login() fetches it, and null if the account genuinely has
    // none assigned.
    @Volatile
    var checkpointCode: String? = null

    @Volatile
    var checkpointName: String? = null

    fun bearerHeader(): String = "Bearer ${accessToken ?: error("Not logged in")}"

    fun isLoggedIn(): Boolean = accessToken != null

    /** Writes the current identity + tokens to the encrypted [SessionStore]
     * so the next app launch can resume without a password. */
    fun persist() {
        val access = accessToken ?: return
        val refresh = refreshToken ?: return
        SessionStore.save(PersistedSession(access, refresh, username, role, checkpointCode, checkpointName, loginAt))
    }

    /** Restores a previously persisted session; returns true if one existed.
     * The tokens may still be expired — the first API call (or the
     * proactive refresh at startup) settles that. */
    fun restore(): Boolean {
        val saved = SessionStore.load() ?: return false
        accessToken = saved.accessToken
        refreshToken = saved.refreshToken
        username = saved.username
        role = saved.role
        checkpointCode = saved.checkpointCode
        checkpointName = saved.checkpointName
        loginAt = saved.loginAt
        return true
    }

    fun updateTokens(access: String, refresh: String) {
        accessToken = access
        refreshToken = refresh
        persist()
    }

    fun clear() {
        accessToken = null
        refreshToken = null
        SessionStore.clear()
        username = null
        role = null
        loginAt = null
        checkpointCode = null
        checkpointName = null
    }
}

/** One-shot notices the login screen shows after an involuntary sign-out
 * ("session expired", "signed out after inactivity"), plus a stream the
 * navigation layer listens to so an expiry detected deep inside a network
 * call still routes the officer back to sign-in. */
object SessionEvents {
    val expired = MutableSharedFlow<Unit>(extraBufferCapacity = 1)

    @Volatile
    var pendingNotice: String? = null

    fun expire(notice: String) {
        pendingNotice = notice
        AuthSession.clear()
        expired.tryEmit(Unit)
    }
}

/** On a 401 for an authenticated request, exchange the stored refresh token
 * for a new pair and retry once. If the refresh token itself is rejected the
 * session is genuinely over → sign out with a clear notice. A network
 * failure during refresh leaves the session alone (the officer may just be
 * offline) rather than wrongly signing them out. */
private class TokenAuthenticator(private val refreshApi: () -> ApiService) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        val sentAuth = response.request.header("Authorization") ?: return null
        if (responseCount(response) >= 2) return null

        synchronized(this) {
            val current = AuthSession.accessToken
            if (current != null && "Bearer $current" != sentAuth) {
                return response.request.newBuilder().header("Authorization", "Bearer $current").build()
            }
            val refresh = AuthSession.refreshToken ?: run {
                SessionEvents.expire("Your session has expired. Please sign in again.")
                return null
            }
            return try {
                val tokens = runBlocking { refreshApi().refresh(RefreshRequest(refresh)) }
                AuthSession.updateTokens(tokens.accessToken, tokens.refreshToken)
                response.request.newBuilder().header("Authorization", "Bearer ${tokens.accessToken}").build()
            } catch (e: HttpException) {
                if (e.code() == 401) SessionEvents.expire("Your session has expired. Please sign in again.")
                null
            } catch (_: IOException) {
                null
            }
        }
    }

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
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

    // OkHttp's default is 10s connect/read/write, which is far too short for
    // this backend: Render's free tier can take 30-50s to wake from a cold
    // start, and the screening pipeline itself (OCR + forensics + face +
    // liveness) can take 20-30s on the free tier's shared CPU even once
    // warm. Generous timeouts here trade a longer worst-case wait for not
    // aborting a request that was actually going to succeed.
    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .writeTimeout(90, TimeUnit.SECONDS)
        .authenticator(TokenAuthenticator { plainApiService })
        .build()

    // No authenticator here — the refresh call itself must never recurse
    // into another refresh attempt.
    private val plainClient = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val plainApiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(plainClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }

    val apiService: ApiService by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create(gson))
            .build()
            .create(ApiService::class.java)
    }
}
