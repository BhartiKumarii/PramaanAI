package com.pramaanai.officer.ui.history

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class StatusFilter(val labelRes: Int) {
    ALL(R.string.filter_all),
    PENDING(R.string.filter_pending),
    CLEARED(R.string.filter_cleared),
    DISPUTED(R.string.filter_disputed),
}

@Composable
fun HistoryScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val items by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.syncFromBackend() }
    var query by remember { mutableStateOf("") }
    var statusFilter by remember { mutableStateOf(StatusFilter.ALL) }

    val filtered = remember(items, query, statusFilter) {
        items
            .filter { statusFilter == StatusFilter.ALL || it.status.name == statusFilter.name }
            .filter {
                query.isBlank() ||
                    it.travelerName.contains(query, ignoreCase = true) ||
                    it.nationality.contains(query, ignoreCase = true) ||
                    it.id.contains(query, ignoreCase = true)
            }
    }

    Column(modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp)) {
        Spacer(Modifier.height(4.dp))
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            placeholder = { Text(stringResource(R.string.history_search_placeholder)) },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusFilter.entries.forEach { f ->
                FilterChip(selected = statusFilter == f, onClick = { statusFilter = f }, label = { Text(stringResource(f.labelRes)) })
            }
        }
        Spacer(Modifier.height(8.dp))
        if (filtered.isEmpty()) {
            EmptyState(stringResource(R.string.history_empty_title), stringResource(R.string.history_empty_subtitle))
        } else {
            LazyColumn(modifier = Modifier.fillMaxSize()) {
                items(filtered, key = { it.id }) { item ->
                    HistoryRow(item, onClick = { onOpenScreening(item.id) })
                    Spacer(Modifier.height(8.dp))
                }
            }
        }
    }
}

@Composable
private fun HistoryRow(item: ScreeningQueueItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = androidx.compose.material3.CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column(Modifier.weight(1f)) {
                    Text(item.travelerName, fontWeight = FontWeight.SemiBold)
                    Text(
                        "${item.documentType.replace("_", " ")} · ${item.nationality}",
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray500,
                    )
                }
                RiskBadge(level = item.risk?.level ?: "PENDING")
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "${item.status.name} · ${SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(item.submittedAt))}" +
                    (item.decidingOfficer?.let { " · by $it" } ?: ""),
                style = MaterialTheme.typography.labelSmall,
                color = Gray500,
            )
        }
    }
}
