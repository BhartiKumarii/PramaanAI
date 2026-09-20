package com.pramaanai.officer.ui.review

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.R
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.workflow.signalTitle

// Shared by the Screening Review screen and the workflow's Officer Review
// step: a flag or hand-off records what the system itself found, so an
// officer never has to write a reason from scratch.

/** What the system itself raised on this screening, worst first — used as the
 * recorded reason for a flag or a hand-off, so an officer never has to write
 * one from scratch. Only signals that actually contributed risk are listed. */
fun flaggedReasons(ctx: Context, item: ScreeningQueueItem): List<String> {
    val risk = item.risk
    val fromSignals = risk?.breakdown.orEmpty()
        .filter { it.rawRisk > 0.0001 }
        .sortedByDescending { it.contribution }
        .map { "${signalTitle(it.signal)}: ${it.reason}" }
    val head = risk?.topReason?.takeIf { it.startsWith("hard override") }?.let { listOf(it.removePrefix("hard override: ").replaceFirstChar { c -> c.uppercase() }) }.orEmpty()
    val all = (head.filter { h -> fromSignals.none { it.contains(h, ignoreCase = true) } } + fromSignals).distinct().take(6)
    return all.ifEmpty { listOf(ctx.getString(R.string.flag_officer_initiated)) }
}

fun friendlyActionError(ctx: Context, action: String, e: Exception): String = when {
    e is java.io.IOException -> ctx.getString(R.string.error_no_connection, action)
    e.message?.contains("no backend case") == true -> ctx.getString(R.string.error_not_synced)
    e is retrofit2.HttpException && e.code() == 409 -> ctx.getString(R.string.error_already_decided, action)
    else -> ctx.getString(R.string.error_generic_action, action, e.message ?: ctx.getString(R.string.error_unexpected))
}

@Composable
fun ReasonDialog(
    title: String,
    intro: String,
    reasons: List<String>,
    confirmLabel: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(modifier = Modifier.verticalScroll(rememberScrollState())) {
                Text(intro, style = MaterialTheme.typography.bodySmall, color = Gray600)
                Spacer(Modifier.height(12.dp))
                reasons.forEach { reason ->
                    Row(modifier = Modifier.padding(vertical = 4.dp)) {
                        Text("•  ", color = AccentGreen, fontWeight = FontWeight.Bold)
                        Text(reason, style = MaterialTheme.typography.bodyMedium)
                    }
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    "A risk alert to support the officer's judgment — not a finding about the traveler.",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                )
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
            ) { Text(confirmLabel) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}
