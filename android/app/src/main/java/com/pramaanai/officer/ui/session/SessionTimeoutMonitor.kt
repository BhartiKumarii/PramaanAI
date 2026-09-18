package com.pramaanai.officer.ui.session

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import kotlinx.coroutines.delay

private const val IDLE_WARNING_AFTER_MS = 10 * 60 * 1000L
private const val WARNING_COUNTDOWN_SECONDS = 30

/** Real idle-session tracking: any touch anywhere in [content] resets the
 * idle clock (a non-consuming pointerInput pass, so it never steals a tap
 * from the actual UI beneath it). After [IDLE_WARNING_AFTER_MS] of no
 * activity, shows a countdown warning before calling [onSessionExpired] —
 * this fires a real logout, not a cosmetic dialog. */
@Composable
fun SessionTimeoutMonitor(
    active: Boolean,
    onSessionExpired: () -> Unit,
    onStaySignedIn: () -> Unit,
    content: @Composable () -> Unit,
) {
    var lastActivityAt by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var showWarning by remember { mutableStateOf(false) }
    var secondsRemaining by remember { mutableStateOf(WARNING_COUNTDOWN_SECONDS) }

    // Only counts while an officer is actually signed in. Running it on the
    // login screen showed a "Session expiring" dialog over the sign-in form,
    // and after an expiry the loop ended while the dialog stayed up with a
    // negative countdown.
    LaunchedEffect(active) {
        showWarning = false
        if (!active) return@LaunchedEffect
        lastActivityAt = System.currentTimeMillis()
        while (true) {
            delay(1000)
            val idleFor = System.currentTimeMillis() - lastActivityAt
            if (idleFor >= IDLE_WARNING_AFTER_MS) {
                showWarning = true
                val overshootSeconds = ((idleFor - IDLE_WARNING_AFTER_MS) / 1000).toInt()
                val remaining = WARNING_COUNTDOWN_SECONDS - overshootSeconds
                secondsRemaining = remaining.coerceAtLeast(0)
                if (remaining <= 0) {
                    showWarning = false
                    onSessionExpired()
                    return@LaunchedEffect
                }
            } else {
                showWarning = false
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .pointerInput(Unit) {
                awaitPointerEventScope {
                    while (true) {
                        awaitPointerEvent(PointerEventPass.Initial)
                        lastActivityAt = System.currentTimeMillis()
                    }
                }
            },
    ) {
        content()
    }

    if (showWarning && active) {
        AlertDialog(
            onDismissRequest = {
                lastActivityAt = System.currentTimeMillis()
                showWarning = false
            },
            title = { Text("Session expiring") },
            text = {
                Column {
                    Text("You've been inactive. For security, this session will end automatically.")
                    Spacer(Modifier.height(8.dp))
                    Text("Signing out in ${secondsRemaining}s", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        lastActivityAt = System.currentTimeMillis()
                        showWarning = false
                        onStaySignedIn()
                    },
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                ) { Text("Stay signed in") }
            },
            dismissButton = {
                TextButton(onClick = {
                    showWarning = false
                    onSessionExpired()
                }) { Text("Log out now") }
            },
        )
    }
}
