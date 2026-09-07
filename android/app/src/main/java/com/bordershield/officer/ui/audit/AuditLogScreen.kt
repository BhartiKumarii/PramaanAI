package com.bordershield.officer.ui.audit

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.model.AuditLogEntry
import com.bordershield.officer.ui.components.EmptyState
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Every important officer action generates an audit entry — real, appended
 * as it happens (see [ScreeningRepository]). Read-only: nothing in this
 * screen edits or deletes an entry. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AuditLogScreen(repository: ScreeningRepository, onBack: () -> Unit) {
    val entries by repository.observeAuditLog().collectAsStateWithLifecycle(initialValue = emptyList())

    Scaffold(topBar = { TopAppBar(title = { Text("Audit Log") }) }) { padding ->
        if (entries.isEmpty()) {
            Column(modifier = Modifier.fillMaxSize().padding(padding)) {
                EmptyState("No audit entries yet", "Officer logins, screenings, and decisions will be recorded here.")
            }
            return@Scaffold
        }
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
            items(entries, key = { it.id }) { entry ->
                AuditRow(entry)
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun AuditRow(entry: AuditLogEntry) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        border = BorderStroke(1.dp, Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(entry.action, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
                Text(
                    SimpleDateFormat("dd MMM, HH:mm:ss", Locale.getDefault()).format(Date(entry.timestamp)),
                    style = MaterialTheme.typography.labelSmall,
                    color = Gray500,
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(entry.result, style = MaterialTheme.typography.bodySmall, color = Gray500)
            Text(
                "Officer: ${entry.officer}" + (entry.record?.let { " · Record: ${it.take(8)}" } ?: ""),
                style = MaterialTheme.typography.labelSmall,
                color = Gray500,
            )
        }
    }
}
