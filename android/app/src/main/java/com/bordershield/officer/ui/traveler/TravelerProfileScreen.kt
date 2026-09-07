package com.bordershield.officer.ui.traveler

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.ui.components.RiskBadge
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TravelerProfileScreen(repository: ScreeningRepository, travelerName: String, onOpenScreening: (String) -> Unit) {
    var records by remember { mutableStateOf<List<ScreeningQueueItem>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }

    LaunchedEffect(travelerName) {
        records = repository.findByTraveler(travelerName)
        loading = false
    }

    Scaffold(topBar = { TopAppBar(title = { Text(travelerName) }) }) { padding ->
        if (loading) {
            Column(modifier = Modifier.fillMaxSize().padding(padding), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }
        val latest = records.firstOrNull()
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            item {
                Section("Identity") {
                    InfoRow("Name", travelerName)
                    InfoRow("Nationality", latest?.nationality ?: "—")
                    InfoRow("Document type", latest?.documentType?.replace("_", " ") ?: "—")
                    InfoRow("Total screenings", "${records.size}")
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Section("Risk Assessments") {
                    if (latest?.risk == null) {
                        Text("No risk assessment on file.", style = MaterialTheme.typography.bodySmall, color = Gray500)
                    } else {
                        records.take(5).forEach { record ->
                            Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                                Text(
                                    SimpleDateFormat("dd MMM yyyy", Locale.getDefault()).format(Date(record.submittedAt)),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                                RiskBadge(level = record.risk?.level ?: "PENDING")
                            }
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Section("Officer Notes") {
                    val notes = records.mapNotNull { it.officerNotes?.let { note -> it.decidingOfficer to note } }
                    if (notes.isEmpty()) {
                        Text("No officer notes recorded.", style = MaterialTheme.typography.bodySmall, color = Gray500)
                    } else {
                        notes.forEach { (officer, note) ->
                            Text("• $note — $officer", style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(vertical = 2.dp))
                        }
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Text("Screening History", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(8.dp))
            }
            items(records, key = { it.id }) { record ->
                TimelineRow(record, onClick = { onOpenScreening(record.id) })
                Spacer(Modifier.height(8.dp))
            }
        }
    }
}

@Composable
private fun Section(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), border = BorderStroke(1.dp, Gray200), shape = RoundedCornerShape(10.dp)) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Gray600)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun TimelineRow(record: ScreeningQueueItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        border = BorderStroke(1.dp, Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Row(modifier = Modifier.fillMaxWidth().padding(12.dp), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Column {
                Text(
                    SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(record.submittedAt)),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                )
                Text("${record.checkpoint} · ${record.status.name}", style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
            RiskBadge(level = record.risk?.level ?: "PENDING")
        }
    }
}
