package com.bordershield.officer.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.computeAnalytics
import com.bordershield.officer.data.dailyActivity
import com.bordershield.officer.data.model.ScreeningQueueItem
import com.bordershield.officer.ui.components.MonoBarChart
import com.bordershield.officer.ui.components.MonoRibbonBar
import com.bordershield.officer.ui.components.RiskBadge
import com.bordershield.officer.ui.tour.tourAnchor
import com.bordershield.officer.ui.theme.Gray100
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White

@Composable
fun DashboardScreen(
    repository: ScreeningRepository,
    padding: PaddingValues,
    onNewScreening: () -> Unit,
    onOpenScreening: (String) -> Unit,
    onViewQueue: () -> Unit,
    onViewHistory: () -> Unit,
    onViewAnalytics: () -> Unit,
) {
    val items by repository.observeQueue().collectAsStateWithLifecycle(initialValue = emptyList())
    val alerts by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
    // Pulls in other officers'/devices' screenings from the shared backend
    // queue — silent no-op if the backend is unreachable, so the local
    // cache this device already has still renders.
    androidx.compose.runtime.LaunchedEffect(Unit) { repository.syncFromBackend() }
    val stats = remember(items) { computeAnalytics(items) }
    var chartRange by remember { mutableStateOf(ChartRange.WEEKLY) }
    val chartData = remember(items, chartRange) {
        dailyActivity(items, if (chartRange == ChartRange.MONTHLY) 30 else 7)
    }

    val listState = androidx.compose.foundation.lazy.rememberLazyListState()
    // A LazyColumn only composes visible items, so an off-screen tour
    // anchor (e.g. the Quick Actions button, several cards down) would
    // never register — scroll it into view whenever the tour steps onto it.
    androidx.compose.runtime.LaunchedEffect(com.bordershield.officer.ui.tour.TourState.stepIndex, com.bordershield.officer.ui.tour.TourState.active) {
        if (!com.bordershield.officer.ui.tour.TourState.active) return@LaunchedEffect
        val targetIndex = when (com.bordershield.officer.ui.tour.TourState.currentStep?.anchorId) {
            "stat_cards" -> 0
            "risk_overview" -> 2
            "new_screening_button" -> 4
            else -> null
        }
        if (targetIndex != null) listState.animateScrollToItem(targetIndex)
    }

    LazyColumn(
        state = listState,
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            LazyVerticalGrid(
                columns = GridCells.Fixed(2),
                modifier = Modifier.height(340.dp).tourAnchor("stat_cards"),
                userScrollEnabled = false,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(
                    listOf(
                        StatCardData("Total Screenings", stats.total),
                        StatCardData("Screenings Today", stats.today, trendPct = stats.todayVsYesterdayPct),
                        StatCardData("High-Risk Cases", stats.highRisk),
                        StatCardData("Pending Reviews", stats.pending),
                        StatCardData("Documents Scanned", stats.documentsScanned),
                        StatCardData("Needs Attention", alerts.size),
                    ),
                ) { data -> StatCard(data) }
            }
        }

        item {
            SectionCard(title = "Screening Activity") {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ChartRange.entries.forEach { range ->
                        FilterChip(
                            selected = chartRange == range,
                            onClick = { chartRange = range },
                            label = { Text(range.label) },
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                if (chartRange == ChartRange.TODAY) {
                    Text("${stats.today}", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
                    Text("screenings submitted today", style = MaterialTheme.typography.bodySmall, color = Gray600)
                } else {
                    MonoBarChart(chartData)
                }
            }
        }

        item {
            SectionCard(title = "Risk Overview", modifier = Modifier.tourAnchor("risk_overview")) {
                Text(
                    "${stats.total} total risk assessments",
                    style = MaterialTheme.typography.bodySmall,
                    color = Gray600,
                )
                Spacer(Modifier.height(10.dp))
                MonoRibbonBar("Low risk", stats.lowRisk, stats.total)
                MonoRibbonBar("Medium risk", stats.mediumRisk, stats.total)
                MonoRibbonBar("High risk", stats.highRisk, stats.total)
            }
        }

        item {
            SectionCard(title = "Recent Screenings") {
                if (items.isEmpty()) {
                    Text("No screenings yet.", style = MaterialTheme.typography.bodySmall, color = Gray600)
                } else {
                    items.take(5).forEach { item -> RecentRow(item, onClick = { onOpenScreening(item.id) }) }
                }
            }
        }

        item {
            SectionCard(title = "Quick Actions") {
                QuickActionButton("+ New Screening", onNewScreening, modifier = Modifier.tourAnchor("new_screening_button"))
                Spacer(Modifier.height(8.dp))
                QuickActionButton("View Screening Queue", onViewQueue)
                Spacer(Modifier.height(8.dp))
                QuickActionButton("View History", onViewHistory)
                Spacer(Modifier.height(8.dp))
                QuickActionButton("View Analytics", onViewAnalytics)
            }
        }
    }
}

private enum class ChartRange(val label: String) { TODAY("Today"), WEEKLY("Weekly"), MONTHLY("Monthly") }

private data class StatCardData(val label: String, val value: Int, val trendPct: Int? = null)

@Composable
private fun StatCard(data: StatCardData) {
    Card(
        modifier = Modifier.fillMaxWidth().aspectRatio(1.6f),
        colors = CardDefaults.cardColors(containerColor = Gray100),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.SpaceBetween) {
            Text(data.label, style = MaterialTheme.typography.labelMedium, color = Gray600)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${data.value}", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = Ink900)
                // Only rendered when a real prior-day baseline exists — never
                // a fabricated trend on a fresh install with no history.
                data.trendPct?.let { pct ->
                    Spacer(Modifier.width(8.dp))
                    val arrow = if (pct >= 0) "▲" else "▼"
                    Text(
                        "$arrow ${kotlin.math.abs(pct)}%",
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = White),
        border = androidx.compose.foundation.BorderStroke(1.dp, com.bordershield.officer.ui.theme.Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

@Composable
private fun RecentRow(item: ScreeningQueueItem, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(item.travelerName, fontWeight = FontWeight.Medium, style = MaterialTheme.typography.bodyMedium)
            Text(
                "${item.nationality} · ${item.documentType.replace("_", " ")} · ${item.status.name}",
                style = MaterialTheme.typography.labelSmall,
                color = Gray500,
            )
        }
        RiskBadge(level = item.risk?.level ?: "PENDING")
    }
}

@Composable
private fun QuickActionButton(label: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    OutlinedButton(
        onClick = onClick,
        modifier = modifier.fillMaxWidth().height(48.dp),
        shape = RoundedCornerShape(8.dp),
        border = androidx.compose.foundation.BorderStroke(1.dp, Ink900),
    ) {
        Text(label, color = Ink900, fontWeight = FontWeight.Medium)
    }
}
