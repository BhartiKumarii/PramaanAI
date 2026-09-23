package com.pramaanai.officer.data.connectivity

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import com.pramaanai.officer.data.remote.ApiService
import kotlinx.coroutines.withTimeoutOrNull

/** Real, live connectivity check — never assumed (see CLAUDE.md: "The
 * Android app runs a live, lightweight health check... each time it
 * needs the server"). ONLINE/WEAK/OFFLINE are the only three states, and
 * this is the only place in the app that produces them — no other
 * screen/component hardcodes a status. */
enum class ConnectivityState { ONLINE, WEAK, OFFLINE }

class ConnectivityMonitor(
    private val context: Context,
    private val api: ApiService,
) {
    private val connectivityManager
        get() = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    /** Fast local signal only — does the OS report an active network with
     * internet capability right now. Doesn't confirm the backend is
     * actually reachable (that's [check]). */
    fun hasNetworkCapability(): Boolean {
        val network = connectivityManager.activeNetwork ?: return false
        val capabilities = connectivityManager.getNetworkCapabilities(network) ?: return false
        return capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    /** The actual live check: OS-reported network presence, PLUS a real
     * GET /health round trip, timed.
     *   ONLINE  — the server answered quickly (< [WEAK_THRESHOLD_MS])
     *   WEAK    — the server answered, but slowly
     *   OFFLINE — no network, or the server could not be reached at all
     * [lastDetail] says which, in plain words, for the status indicator. */
    suspend fun check(): ConnectivityState {
        if (!hasNetworkCapability()) {
            lastDetail = "no network"
            return ConnectivityState.OFFLINE
        }
        val started = System.nanoTime()
        val reachable = withTimeoutOrNull(5_000L) {
            runCatching { api.health() }.isSuccess
        } ?: false
        val elapsedMs = (System.nanoTime() - started) / 1_000_000
        return when {
            !reachable -> ConnectivityState.OFFLINE.also { lastDetail = "server not reachable" }
            elapsedMs >= WEAK_THRESHOLD_MS -> ConnectivityState.WEAK.also { lastDetail = "slow response · ${elapsedMs} ms" }
            else -> ConnectivityState.ONLINE.also { lastDetail = "${elapsedMs} ms" }
        }
    }

    companion object {
        const val WEAK_THRESHOLD_MS = 1_500L

        /** Plain-language reason for the most recent [check] result. */
        @Volatile
        var lastDetail: String = ""
            private set
    }
}
