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
     * GET /health round trip with a short timeout to tell "online" apart
     * from "device thinks it has signal but the backend isn't actually
     * reachable" (weak/flaky connection, captive portal, backend down). */
    suspend fun check(): ConnectivityState {
        if (!hasNetworkCapability()) return ConnectivityState.OFFLINE
        val reachable = withTimeoutOrNull(3_000L) {
            runCatching { api.health() }.isSuccess
        } ?: false
        return if (reachable) ConnectivityState.ONLINE else ConnectivityState.WEAK
    }
}
