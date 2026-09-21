package com.pramaanai.officer.ui.queue

import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBox
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.CreditCard
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.Flight
import androidx.compose.material.icons.filled.Map
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.humanLabel
import com.pramaanai.officer.data.humanTopReason
import com.pramaanai.officer.data.humanSignalTitle
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.ui.components.EmptyState
import com.pramaanai.officer.ui.components.RiskBadge
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.WarningAmber
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class QueueFilter(val labelRes: Int) {
    ALL(R.string.filter_all),
    HIGH_PRIORITY(R.string.filter_high_priority),
    PENDING(R.string.filter_pending),
    RECENT(R.string.filter_recently_created),
}

@Composable
fun QueueScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val items by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.syncFromBackend() }
    var filter by remember { mutableStateOf(QueueFilter.ALL) }

    val filtered = remember(items, filter) {
        val hourAgo = System.currentTimeMillis() - 60 * 60 * 1000
        when (filter) {
            QueueFilter.ALL -> items.sortedByDescending { (if (it.risk?.level == "HIGH_RISK") 3 else if (it.status == ScreeningStatus.PENDING) 2 else 1) * 1_000_000_000L + it.submittedAt }
            QueueFilter.HIGH_PRIORITY -> items.filter { it.risk?.level == "HIGH_RISK" }.sortedByDescending { it.submittedAt }
            QueueFilter.PENDING -> items.filter { it.status == ScreeningStatus.PENDING }.sortedByDescending { it.submittedAt }
            QueueFilter.RECENT -> items.filter { it.submittedAt >= hourAgo }.sortedByDescending { it.submittedAt }
        }
    }

    val highCount = items.count { it.risk?.level == "HIGH_RISK" }
    val pendingCount = items.count { it.status == ScreeningStatus.PENDING }

    Column(modifier = Modifier.fillMaxSize().padding(padding)) {
        // Stats strip
        if (items.isNotEmpty()) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                StatChip(label = "${items.size} total", color = Gray100)
                if (highCount > 0) StatChip(label = "$highCount high risk", color = DestructiveRed.copy(alpha = 0.15f), textColor = DestructiveRed)
                if (pendingCount > 0) StatChip(label = "$pendingCount pending", color = WarningAmber.copy(alpha = 0.15f), textColor = WarningAmber)
            }
        }

        // Filter chips
        LazyRow(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(QueueFilter.entries) { f ->
                FilterChip(
                    selected = filter == f,
                    onClick = { filter = f },
                    label = { Text(stringResource(f.labelRes)) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = AccentGreen.copy(alpha = 0.18f),
                        selectedLabelColor = AccentGreen,
                    ),
                )
            }
        }
        Spacer(Modifier.height(4.dp))

        if (filtered.isEmpty()) {
            EmptyState(stringResource(R.string.queue_empty_title), stringResource(R.string.queue_empty_subtitle))
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { Spacer(Modifier.height(4.dp)) }
                items(filtered, key = { it.id }) { item ->
                    QueueCard(item = item, onClick = { onOpenScreening(item.id) })
                }
                item { Spacer(Modifier.height(8.dp)) }
            }
        }
    }
}

@Composable
private fun StatChip(label: String, color: androidx.compose.ui.graphics.Color, textColor: androidx.compose.ui.graphics.Color = Ink900) {
    Box(
        modifier = Modifier
            .background(color, RoundedCornerShape(6.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp),
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = textColor, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun QueueCard(item: ScreeningQueueItem, onClick: () -> Unit) {
    val isHighRisk = item.risk?.level == "HIGH_RISK"
    val hasRegistryHit = item.registryHits.isNotEmpty()
    val hasIdentityCluster = item.identityGraph?.status == "CLUSTER_FOUND"

    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(
            1.dp,
            if (isHighRisk) DestructiveRed.copy(alpha = 0.5f) else BorderDark,
        ),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Row 1: Document icon + name + risk badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Row(modifier = Modifier.weight(1f), verticalAlignment = Alignment.CenterVertically) {
                    DocTypeIcon(item.documentType)
                    Spacer(Modifier.width(10.dp))
                    Column {
                        Text(item.travelerName, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                        Text(
                            docTypeLabel(item.documentType) + " · " + item.nationality.uppercase(),
                            style = MaterialTheme.typography.labelSmall,
                            color = Gray600,
                        )
                    }
                }
                RiskBadge(level = item.risk?.level ?: "PENDING")
            }

            Spacer(Modifier.height(10.dp))

            // Row 2: Extracted OCR fields
            val fields = item.ocr?.fields ?: emptyMap()
            val docNum = fields["document_number"]
            val dob = fields["date_of_birth"]
            val expiry = fields["date_of_expiry"]
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                if (docNum != null) FieldPill("Doc No", docNum)
                if (dob != null) FieldPill("DOB", dob)
                if (expiry != null) FieldPill("Expiry", expiry)
            }

            // Row 3: Top reason
            val reason = humanTopReason(item.risk?.topReason)
            if (reason != null) {
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (isHighRisk) {
                        Icon(Icons.Filled.Warning, contentDescription = null, tint = DestructiveRed, modifier = Modifier.size(13.dp))
                        Spacer(Modifier.width(4.dp))
                    }
                    Text(reason, style = MaterialTheme.typography.bodySmall, color = if (isHighRisk) DestructiveRed else Gray500)
                }
            }

            // Row 4: Signal chips (top 3 that fired)
            val signals = item.risk?.breakdown?.filter { it.rawRisk > 0.001 }?.sortedByDescending { it.contribution }?.take(3)
            if (!signals.isNullOrEmpty()) {
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    signals.forEach { s ->
                        SignalChip(humanSignalTitle(s.signal))
                    }
                }
            }

            // Row 5: Identity graph + registry hit indicators
            if (hasIdentityCluster || hasRegistryHit) {
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    if (hasRegistryHit) {
                        Row(
                            modifier = Modifier
                                .background(DestructiveRed.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
                                .padding(horizontal = 8.dp, vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Icon(Icons.Filled.Warning, contentDescription = null, tint = DestructiveRed, modifier = Modifier.size(11.dp))
                            Text("Registry Hit", style = MaterialTheme.typography.labelSmall, color = DestructiveRed, fontWeight = FontWeight.SemiBold)
                        }
                    }
                    if (hasIdentityCluster) {
                        val size = item.identityGraph?.clusterSize ?: 0
                        Row(
                            modifier = Modifier
                                .background(WarningAmber.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
                                .padding(horizontal = 8.dp, vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Icon(Icons.Filled.Share, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(11.dp))
                            Text("Identity linked to $size record${if (size != 1) "s" else ""}", style = MaterialTheme.typography.labelSmall, color = WarningAmber, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }

            Spacer(Modifier.height(8.dp))
            // Footer: status + checkpoint + time
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "${item.status.humanLabel()} · ${item.checkpoint}",
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                )
                Text(timeAgo(item.submittedAt), style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
        }
    }
}

@Composable
private fun DocTypeIcon(docType: String) {
    val icon: ImageVector = when {
        docType.contains("passport", ignoreCase = true) -> Icons.Filled.AccountBox
        docType.contains("visa", ignoreCase = true) -> Icons.Filled.Flight
        docType.contains("driving", ignoreCase = true) || docType.contains("licence", ignoreCase = true) -> Icons.Filled.DirectionsCar
        docType.contains("national", ignoreCase = true) || docType.contains("id", ignoreCase = true) -> Icons.Filled.CreditCard
        docType.contains("permit", ignoreCase = true) || docType.contains("ilp", ignoreCase = true) -> Icons.Filled.Map
        else -> Icons.Filled.Badge
    }
    Box(
        modifier = Modifier
            .size(38.dp)
            .background(AccentGreen.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
            .clip(RoundedCornerShape(8.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = AccentGreen, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun FieldPill(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Gray600)
        Text(value, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium, color = Ink900)
    }
}

@Composable
private fun SignalChip(label: String) {
    Text(
        label,
        style = MaterialTheme.typography.labelSmall,
        color = Gray600,
        modifier = Modifier
            .background(Gray100, RoundedCornerShape(4.dp))
            .padding(horizontal = 7.dp, vertical = 3.dp),
    )
}

private fun docTypeLabel(raw: String): String =
    raw.replace("_", " ").split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }

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
