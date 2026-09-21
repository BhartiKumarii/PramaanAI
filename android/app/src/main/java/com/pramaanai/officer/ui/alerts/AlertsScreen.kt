package com.pramaanai.officer.ui.alerts

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Block
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.PersonOff
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.humanTopReason
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.ui.components.EmptyState
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.data.local.ReadAlertsStore
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class AlertType(val icon: ImageVector, val label: String, val color: Color) {
    BLACKLIST(Icons.Filled.Block, "Blacklist Hit", DestructiveRed),
    EXPIRED(Icons.Filled.Schedule, "Expired Document", WarningAmber),
    IDENTITY_MISMATCH(Icons.Filled.PersonOff, "Identity Mismatch", WarningAmber),
    IDENTITY_CLUSTER(Icons.Filled.Share, "Identity Link Found", WarningAmber),
    HIGH_RISK(Icons.Filled.Warning, "High Risk", DestructiveRed),
}

private data class RichAlert(
    val item: ScreeningQueueItem,
    val alertType: AlertType,
    val headline: String,
    val detail: String,
)

private fun buildAlerts(items: List<ScreeningQueueItem>): List<RichAlert> {
    val alerts = mutableListOf<RichAlert>()
    items.filter { it.risk?.level == "HIGH_RISK" }.sortedByDescending { it.submittedAt }.forEach { item ->
        val topReason = humanTopReason(item.risk?.topReason)
        val docNum = item.ocr?.fields?.get("document_number") ?: ""

        // Blacklist hit
        if (item.registryHits.isNotEmpty()) {
            val hit = item.registryHits.first()
            alerts.add(RichAlert(
                item, AlertType.BLACKLIST,
                "Document on watchlist: ${hit.documentNumber.ifBlank { docNum }}",
                hit.registryReason.ifBlank { "This document number is flagged in the central registry" },
            ))
            return@forEach
        }

        // Check top reason for clues
        val raw = item.risk?.topReason?.lowercase() ?: ""
        when {
            raw.contains("expir") -> alerts.add(RichAlert(
                item, AlertType.EXPIRED,
                "Document has expired",
                topReason ?: "The document expiry date is in the past — entry not permitted without valid travel document",
            ))
            raw.contains("different identity") || raw.contains("identity") -> alerts.add(RichAlert(
                item, AlertType.IDENTITY_MISMATCH,
                "Identity details do not match registry",
                topReason ?: "Name, date of birth, or nationality declared does not match the record on file for this document number",
            ))
            item.identityGraph?.status == "CLUSTER_FOUND" -> alerts.add(RichAlert(
                item, AlertType.IDENTITY_CLUSTER,
                "This identity is linked to ${item.identityGraph.clusterSize} other records",
                "Face biometric or document data matches ${item.identityGraph.clusterSize} prior screening(s) under different identities — officer review required",
            ))
            else -> alerts.add(RichAlert(
                item, AlertType.HIGH_RISK,
                "High risk — officer review required",
                topReason ?: "Multiple risk signals detected — see full screening for details",
            ))
        }
    }
    return alerts
}

@Composable
fun AlertsScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val items by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.syncFromBackend() }

    val context = LocalContext.current
    val readStore = ReadAlertsStore.getInstance(context)
    val readIds by readStore.readIds.collectAsStateWithLifecycle()

    val richAlerts = androidx.compose.runtime.remember(items) { buildAlerts(items) }
    val unreadCount = richAlerts.count { it.item.id !in readIds }

    if (richAlerts.isEmpty()) {
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            EmptyState(
                stringResource(R.string.alerts_empty_title),
                "No high-risk screenings in your current queue. All documents are within expected parameters.",
            )
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item(key = "header") {
            Column {
                Spacer(Modifier.height(8.dp))
                // Summary header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text(
                            "${richAlerts.size} Active Alert${if (richAlerts.size != 1) "s" else ""}",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            color = Ink900,
                        )
                        Text(
                            "$unreadCount unread",
                            style = MaterialTheme.typography.labelSmall,
                            color = Gray500,
                        )
                    }
                    if (unreadCount > 0) {
                        TextButton(onClick = { readStore.markAllRead(richAlerts.map { it.item.id }) }) {
                            Text(stringResource(R.string.alerts_mark_all_read), color = AccentGreen)
                        }
                    }
                }

                Spacer(Modifier.height(8.dp))
                // Category summary pills
                val blacklistCount = richAlerts.count { it.alertType == AlertType.BLACKLIST }
                val expiredCount = richAlerts.count { it.alertType == AlertType.EXPIRED }
                val mismatchCount = richAlerts.count { it.alertType == AlertType.IDENTITY_MISMATCH || it.alertType == AlertType.IDENTITY_CLUSTER }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (blacklistCount > 0) CategoryPill("$blacklistCount Blacklist", DestructiveRed, Icons.Filled.Block)
                    if (expiredCount > 0) CategoryPill("$expiredCount Expired", WarningAmber, Icons.Filled.Schedule)
                    if (mismatchCount > 0) CategoryPill("$mismatchCount Identity", WarningAmber, Icons.Filled.PersonOff)
                }
                Spacer(Modifier.height(8.dp))
                HorizontalDivider(color = BorderDark)
                Spacer(Modifier.height(4.dp))
            }
        }

        items(richAlerts, key = { it.item.id }) { alert ->
            val isRead = alert.item.id in readIds
            AlertCard(
                alert = alert,
                isRead = isRead,
                onClick = {
                    readStore.markRead(alert.item.id)
                    onOpenScreening(alert.item.id)
                },
            )
        }
        item { Spacer(Modifier.height(8.dp)) }
    }
}

@Composable
private fun CategoryPill(label: String, color: Color, icon: ImageVector) {
    Row(
        modifier = Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(11.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = color, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun AlertCard(alert: RichAlert, isRead: Boolean, onClick: () -> Unit) {
    val item = alert.item
    val fields = item.ocr?.fields ?: emptyMap()
    val alertColor = alert.alertType.color

    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (isRead) CardDark else alertColor.copy(alpha = 0.04f),
        ),
        border = BorderStroke(1.dp, if (isRead) BorderDark else alertColor.copy(alpha = 0.45f)),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Alert type banner
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Row(
                    modifier = Modifier
                        .background(alertColor.copy(alpha = 0.15f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(5.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(alert.alertType.icon, contentDescription = null, tint = alertColor, modifier = Modifier.size(13.dp))
                    Text(alert.alertType.label.uppercase(), style = MaterialTheme.typography.labelSmall, color = alertColor, fontWeight = FontWeight.Bold)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (!isRead) {
                        Box(modifier = Modifier.size(7.dp).background(AccentGreen, RoundedCornerShape(50)))
                    }
                    Text(timeAgo(item.submittedAt), style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }

            Spacer(Modifier.height(10.dp))

            // Headline
            Text(alert.headline, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium, color = Ink900)
            Spacer(Modifier.height(4.dp))
            Text(alert.detail, style = MaterialTheme.typography.bodySmall, color = Gray500)

            Spacer(Modifier.height(10.dp))
            HorizontalDivider(color = BorderDark)
            Spacer(Modifier.height(10.dp))

            // Document details
            Text("Document Details", style = MaterialTheme.typography.labelSmall, color = Gray600, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(6.dp))
            val docType = item.documentType.replace("_", " ").split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }
            AlertDetailRow("Traveler", item.travelerName)
            AlertDetailRow("Doc Type", docType)
            AlertDetailRow("Nationality", item.nationality.uppercase())
            fields["document_number"]?.let { AlertDetailRow("Doc Number", it) }
            fields["date_of_expiry"]?.let { AlertDetailRow("Expiry Date", it) }
            fields["date_of_birth"]?.let { AlertDetailRow("Date of Birth", it) }
            AlertDetailRow("Checkpoint", item.checkpoint)
            AlertDetailRow("Scanned", SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(item.submittedAt)))

            // Registry hits
            if (item.registryHits.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                HorizontalDivider(color = BorderDark)
                Spacer(Modifier.height(8.dp))
                Text("Registry Flags", style = MaterialTheme.typography.labelSmall, color = DestructiveRed, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                item.registryHits.forEach { hit ->
                    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Icon(Icons.Filled.Block, contentDescription = null, tint = DestructiveRed, modifier = Modifier.size(12.dp).padding(top = 2.dp))
                        Column {
                            Text(hit.fullName, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium, color = Ink900)
                            Text(hit.registryReason, style = MaterialTheme.typography.labelSmall, color = Gray500)
                        }
                    }
                    Spacer(Modifier.height(4.dp))
                }
            }

            // Identity graph connections
            if (item.identityGraph?.status == "CLUSTER_FOUND" && item.identityGraph.members.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                HorizontalDivider(color = BorderDark)
                Spacer(Modifier.height(8.dp))
                Text("Identity Connections", style = MaterialTheme.typography.labelSmall, color = WarningAmber, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                item.identityGraph.members.take(4).forEach { member ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                        modifier = Modifier.padding(vertical = 2.dp),
                    ) {
                        Icon(Icons.Filled.Share, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(11.dp))
                        Text(member.referenceName, style = MaterialTheme.typography.labelSmall, color = Ink900, fontWeight = FontWeight.Medium)
                        if (member.documentNumber != null) {
                            Text("· ${member.documentNumber}", style = MaterialTheme.typography.labelSmall, color = Gray500)
                        }
                    }
                }
                if (item.identityGraph.members.size > 4) {
                    Text("+${item.identityGraph.members.size - 4} more connections", style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }

            // Risk score
            item.risk?.score?.let { score ->
                Spacer(Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    Box(
                        modifier = Modifier
                            .background(alertColor.copy(alpha = 0.15f), RoundedCornerShape(6.dp))
                            .padding(horizontal = 8.dp, vertical = 3.dp),
                    ) {
                        Text("Risk Score: $score/100", style = MaterialTheme.typography.labelSmall, color = alertColor, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
private fun AlertDetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Gray600, modifier = Modifier.width(90.dp))
        Text(value, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium, color = Ink900)
    }
}

private fun timeAgo(timestamp: Long): String {
    val diffMs = System.currentTimeMillis() - timestamp
    val minutes = diffMs / (60 * 1000)
    return when {
        minutes < 1 -> "just now"
        minutes < 60 -> "${minutes}m ago"
        minutes < 60 * 24 -> "${minutes / 60}h ago"
        else -> SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(timestamp))
    }
}
