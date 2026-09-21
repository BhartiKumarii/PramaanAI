package com.pramaanai.officer.ui.history

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.WifiOff
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.humanSignalTitle
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.ui.components.EmptyState
import com.pramaanai.officer.ui.components.RiskBadge
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

private enum class HistoryFilter(val labelRes: Int) {
    ALL(R.string.filter_all),
    CLEARED(R.string.filter_cleared),
    HIGH_RISK(R.string.filter_high_priority),
    SENT(R.string.filter_submitted),
}

@Composable
fun HistoryScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val allItems by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.syncFromBackend() }
    var query by remember { mutableStateOf("") }
    var historyFilter by remember { mutableStateOf(HistoryFilter.ALL) }

    val filtered = remember(allItems, query, historyFilter) {
        allItems
            .sortedByDescending { it.submittedAt }
            .filter { item ->
                when (historyFilter) {
                    HistoryFilter.ALL -> true
                    HistoryFilter.CLEARED -> item.status == ScreeningStatus.CLEARED
                    HistoryFilter.HIGH_RISK -> item.risk?.level == "HIGH_RISK"
                    HistoryFilter.SENT -> item.status == ScreeningStatus.SENT
                }
            }
            .filter { item ->
                if (query.isBlank()) true
                else {
                    val docNum = item.ocr?.fields?.get("document_number") ?: ""
                    item.travelerName.contains(query, ignoreCase = true) ||
                        item.nationality.contains(query, ignoreCase = true) ||
                        docNum.contains(query, ignoreCase = true) ||
                        item.documentType.contains(query, ignoreCase = true)
                }
            }
    }

    // Group by day bucket
    val grouped = remember(filtered) {
        val now = Calendar.getInstance()
        val today = now.clone() as Calendar
        today.set(Calendar.HOUR_OF_DAY, 0); today.set(Calendar.MINUTE, 0); today.set(Calendar.SECOND, 0)
        val yesterday = today.clone() as Calendar; yesterday.add(Calendar.DAY_OF_YEAR, -1)
        val weekAgo = today.clone() as Calendar; weekAgo.add(Calendar.DAY_OF_YEAR, -7)

        fun bucket(ts: Long): String {
            val c = Calendar.getInstance().also { it.timeInMillis = ts }
            return when {
                c.timeInMillis >= today.timeInMillis -> "Today"
                c.timeInMillis >= yesterday.timeInMillis -> "Yesterday"
                c.timeInMillis >= weekAgo.timeInMillis -> "This Week"
                else -> SimpleDateFormat("MMMM yyyy", Locale.getDefault()).format(Date(ts))
            }
        }
        filtered.groupBy { bucket(it.submittedAt) }
    }

    // Stats for today
    val todayStart = Calendar.getInstance().apply {
        set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0)
    }.timeInMillis
    val todayItems = allItems.filter { it.submittedAt >= todayStart }

    Column(modifier = Modifier.fillMaxSize().padding(padding)) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            Spacer(Modifier.height(8.dp))
            // Today stats bar
            if (allItems.isNotEmpty()) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    StatBox("Today", todayItems.size.toString(), modifier = Modifier.weight(1f))
                    StatBox("Total", allItems.size.toString(), modifier = Modifier.weight(1f))
                    StatBox("High Risk", allItems.count { it.risk?.level == "HIGH_RISK" }.toString(), modifier = Modifier.weight(1f), highlight = true)
                }
                Spacer(Modifier.height(10.dp))
            }
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                placeholder = { Text("Search by name, doc number, nationality…") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                HistoryFilter.entries.forEach { f ->
                    FilterChip(
                        selected = historyFilter == f,
                        onClick = { historyFilter = f },
                        label = { Text(stringResource(f.labelRes)) },
                        colors = FilterChipDefaults.filterChipColors(
                            selectedContainerColor = AccentGreen.copy(alpha = 0.18f),
                            selectedLabelColor = AccentGreen,
                        ),
                    )
                }
            }
            Spacer(Modifier.height(4.dp))
        }

        if (filtered.isEmpty()) {
            EmptyState(stringResource(R.string.history_empty_title), stringResource(R.string.history_empty_subtitle))
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp)) {
                grouped.forEach { (bucket, bucketItems) ->
                    item(key = "header_$bucket") {
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            HorizontalDivider(modifier = Modifier.weight(1f), color = Gray200)
                            Text(bucket, style = MaterialTheme.typography.labelSmall, color = Gray500, fontWeight = FontWeight.SemiBold)
                            HorizontalDivider(modifier = Modifier.weight(1f), color = Gray200)
                        }
                    }
                    items(bucketItems, key = { it.id }) { item ->
                        HistoryCard(item = item, onClick = { onOpenScreening(item.id) })
                        Spacer(Modifier.height(10.dp))
                    }
                }
                item { Spacer(Modifier.height(8.dp)) }
            }
        }
    }
}

@Composable
private fun StatBox(label: String, value: String, modifier: Modifier = Modifier, highlight: Boolean = false) {
    Box(
        modifier = modifier
            .background(
                if (highlight && value != "0") DestructiveRed.copy(alpha = 0.08f) else Gray100,
                RoundedCornerShape(8.dp),
            )
            .padding(horizontal = 10.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(value, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold,
                color = if (highlight && value != "0") DestructiveRed else Ink900)
            Text(label, style = MaterialTheme.typography.labelSmall, color = Gray600)
        }
    }
}

@Composable
private fun HistoryCard(item: ScreeningQueueItem, onClick: () -> Unit) {
    val fields = item.ocr?.fields ?: emptyMap()

    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            // Header: name + time + risk
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(item.travelerName, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                    Text(
                        SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(item.submittedAt)),
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray500,
                    )
                }
                RiskBadge(level = item.risk?.level ?: "PENDING")
            }

            Spacer(Modifier.height(10.dp))
            HorizontalDivider(color = BorderDark)
            Spacer(Modifier.height(10.dp))

            // Extracted document details grid
            val docType = item.documentType.replace("_", " ").split(" ").joinToString(" ") { it.replaceFirstChar { c -> c.uppercase() } }
            DetailRow("Document Type", docType)
            DetailRow("Nationality", item.nationality.uppercase())
            DetailRow("Checkpoint", item.checkpoint)
            fields["document_number"]?.let { DetailRow("Document No.", it) }
            fields["date_of_birth"]?.let { DetailRow("Date of Birth", it) }
            fields["date_of_expiry"]?.let { DetailRow("Expiry", it) }
            fields["gender"]?.let { DetailRow("Gender", it.replaceFirstChar { c -> c.uppercase() }) }

            item.ocr?.ocrConfidence?.takeIf { it > 0 }?.let {
                DetailRow("Text Read Quality", "${(it * 100).toInt()}%")
            }

            // Validation findings summary
            val failed = item.validation?.findings?.filter { it.status == "FAIL" }
            if (!failed.isNullOrEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Validation issues", style = MaterialTheme.typography.labelSmall, color = Gray600, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                failed.take(3).forEach { finding ->
                    Text("• ${finding.check}: ${finding.reason}", style = MaterialTheme.typography.labelSmall, color = WarningAmber)
                }
            }

            // Active signals
            val activeSignals = item.risk?.breakdown?.filter { it.rawRisk > 0.001 }?.sortedByDescending { it.contribution }
            if (!activeSignals.isNullOrEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Signals detected", style = MaterialTheme.typography.labelSmall, color = Gray600, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                activeSignals.take(4).forEach { s ->
                    Text("• ${humanSignalTitle(s.signal)}", style = MaterialTheme.typography.labelSmall, color = Gray500)
                }
            }

            // Identity graph
            if (item.identityGraph?.status == "CLUSTER_FOUND") {
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier
                        .background(WarningAmber.copy(alpha = 0.1f), RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.Info, contentDescription = null, tint = WarningAmber, modifier = Modifier.size(13.dp))
                    Text(
                        "Identity linked to ${item.identityGraph.clusterSize} other record${if (item.identityGraph.clusterSize != 1) "s" else ""}",
                        style = MaterialTheme.typography.labelSmall,
                        color = WarningAmber,
                    )
                }
            }

            Spacer(Modifier.height(8.dp))
            // Status pill
            StatusPill(item.status)
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Gray600)
        Text(value, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Medium, color = Ink900)
    }
}

@Composable
private fun StatusPill(status: ScreeningStatus) {
    val triple = when (status) {
        ScreeningStatus.CLEARED -> Triple(Icons.Filled.CheckCircle, "Verified", SuccessGreen)
        ScreeningStatus.SENT -> Triple(Icons.Filled.Send, "Submitted for Review", AccentGreen)
        ScreeningStatus.PENDING -> Triple(Icons.Filled.Info, "Pending", WarningAmber)
        ScreeningStatus.OFFLINE_QUEUED -> Triple(Icons.Filled.WifiOff, "Offline — Queued", Gray500)
        ScreeningStatus.DISPUTED -> Triple(Icons.Filled.Info, "Disputed", DestructiveRed)
    }
    val icon = triple.first
    val label = triple.second
    val color = triple.third
    Row(
        modifier = Modifier
            .background(color.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(13.dp))
        Text(label, style = MaterialTheme.typography.labelSmall, color = color, fontWeight = FontWeight.SemiBold)
    }
}
