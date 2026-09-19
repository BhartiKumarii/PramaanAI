package com.pramaanai.officer.ui.queue

import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.data.model.ScreeningStatus
import com.pramaanai.officer.ui.components.EmptyState
import com.pramaanai.officer.ui.components.RiskBadge
import androidx.compose.ui.res.stringResource
import com.pramaanai.officer.R
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
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
            QueueFilter.ALL -> items
            QueueFilter.HIGH_PRIORITY -> items.filter { it.risk?.level == "HIGH_RISK" }
            QueueFilter.PENDING -> items.filter { it.status == ScreeningStatus.PENDING }
            QueueFilter.RECENT -> items.filter { it.submittedAt >= hourAgo }
        }
    }

    Column(modifier = Modifier.fillMaxSize().padding(padding)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            QueueFilter.entries.forEach { f ->
                FilterChip(selected = filter == f, onClick = { filter = f }, label = { Text(stringResource(f.labelRes)) })
            }
        }
        if (filtered.isEmpty()) {
            EmptyState(stringResource(R.string.queue_empty_title), stringResource(R.string.queue_empty_subtitle))
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 12.dp),
            ) {
                items(filtered, key = { it.id }) { item ->
                    QueueRow(item = item, onClick = { onOpenScreening(item.id) })
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun QueueRow(item: ScreeningQueueItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {
                    Text(item.travelerName, fontWeight = FontWeight.SemiBold)
                    Text(
                        "${item.documentType.replaceFirstChar { it.uppercase() }} · ${item.nationality} · ${item.checkpoint}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray600,
                    )
                }
                RiskBadge(level = item.risk?.level ?: "PENDING")
            }
            Spacer(Modifier.height(8.dp))
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text(item.risk?.topReason ?: stringResource(R.string.queue_awaiting_decision), style = MaterialTheme.typography.labelSmall, color = Gray500, modifier = Modifier.weight(1f))
                Text(timeAgo(item.submittedAt, androidx.compose.ui.platform.LocalContext.current.resources), style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
            Spacer(Modifier.height(4.dp))
            // Built-in sample records (ids "mock-N") are synthetic — say so on the card,
            // not just in the id, so they are never mistaken for a real screening.
            val demoTag = if (item.id.startsWith("mock-")) " · DEMO DATA (synthetic)" else ""
            Text("${stringResource(R.string.queue_status_prefix)}${item.status.name} · ID ${item.id.take(8)}$demoTag", style = MaterialTheme.typography.labelSmall, color = Gray500)
        }
    }
}

private fun timeAgo(timestamp: Long, res: android.content.res.Resources): String {
    val diffMs = System.currentTimeMillis() - timestamp
    val minutes = diffMs / (60 * 1000)
    return when {
        minutes < 1 -> res.getString(R.string.time_just_now)
        minutes < 60 -> res.getString(R.string.time_minutes_ago, minutes.toInt())
        minutes < 60 * 24 -> res.getString(R.string.time_hours_ago, (minutes / 60).toInt())
        else -> SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(timestamp))
    }
}
