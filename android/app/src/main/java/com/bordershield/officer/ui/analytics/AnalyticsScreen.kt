package com.bordershield.officer.ui.analytics

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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.computeAnalytics
import com.bordershield.officer.data.dailyActivity
import com.bordershield.officer.ui.components.MonoBarChart
import com.bordershield.officer.ui.components.MonoRibbonBar
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray600

private enum class Range(val label: String, val days: Int) { TODAY("Today", 1), WEEKLY("Weekly", 7), MONTHLY("Monthly", 30) }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnalyticsScreen(repository: ScreeningRepository, onBack: () -> Unit) {
    val items by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    var range by remember { mutableStateOf(Range.WEEKLY) }
    val stats = remember(items) { computeAnalytics(items) }
    val chart = remember(items, range) { dailyActivity(items, range.days.coerceAtLeast(2)) }

    Scaffold(topBar = { TopAppBar(title = { Text("Analytics") }) }) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Range.entries.forEach { r -> FilterChip(selected = range == r, onClick = { range = r }, label = { Text(r.label) }) }
                }
                Spacer(Modifier.height(16.dp))
            }
            item {
                Section("Volume") {
                    InfoRow("Total screenings", "${stats.total}")
                    InfoRow("This period", "${if (range == Range.MONTHLY) stats.thisMonth else if (range == Range.WEEKLY) stats.thisWeek else stats.today}")
                    Spacer(Modifier.height(8.dp))
                    MonoBarChart(chart)
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Section("Risk Distribution") {
                    MonoRibbonBar("Low risk", stats.lowRisk, stats.total)
                    MonoRibbonBar("Medium risk", stats.mediumRisk, stats.total)
                    MonoRibbonBar("High risk", stats.highRisk, stats.total)
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Section("Case Status") {
                    InfoRow("Pending cases", "${stats.pending}")
                    InfoRow("Completed cases", "${stats.cleared + stats.disputed}")
                    InfoRow("Review rate (disputed / decided)", "${(stats.reviewRate * 100).toInt()}%")
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                Section("Notes") {
                    Text(
                        "Average processing time and location-matching statistics are not tracked in " +
                            "this build — no start/end timestamps or location-match signal exist yet to " +
                            "compute them honestly, so they're omitted rather than estimated.",
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
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
