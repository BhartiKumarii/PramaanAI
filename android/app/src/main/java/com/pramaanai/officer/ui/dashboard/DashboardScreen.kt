package com.pramaanai.officer.ui.dashboard

import com.pramaanai.officer.ui.theme.CardDark
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.PendingActions
import androidx.compose.material.icons.filled.Today
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.humanLabel
import com.pramaanai.officer.data.humanTopReason
import com.pramaanai.officer.data.computeAnalytics
import com.pramaanai.officer.data.dailyActivity
import com.pramaanai.officer.data.hourlyActivity
import com.pramaanai.officer.data.model.ScreeningQueueItem
import com.pramaanai.officer.ui.components.MonoBarChart
import com.pramaanai.officer.ui.components.MonoRibbonBar
import com.pramaanai.officer.ui.components.RiskBadge
import com.pramaanai.officer.ui.tour.tourAnchor
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.White

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
        when (chartRange) {
            ChartRange.TODAY -> hourlyActivity(items)
            ChartRange.WEEKLY -> dailyActivity(items, 7)
            ChartRange.MONTHLY -> dailyActivity(items, 30)
        }
    }

    val listState = androidx.compose.foundation.lazy.rememberLazyListState()
    // A LazyColumn only composes visible items, so an off-screen tour
    // anchor (e.g. the Quick Actions button, several cards down) would
    // never register — scroll it into view whenever the tour steps onto it.
    androidx.compose.runtime.LaunchedEffect(com.pramaanai.officer.ui.tour.TourState.stepIndex, com.pramaanai.officer.ui.tour.TourState.active) {
        if (!com.pramaanai.officer.ui.tour.TourState.active) return@LaunchedEffect
        val targetIndex = when (com.pramaanai.officer.ui.tour.TourState.currentStep?.anchorId) {
            "stat_cards" -> 0
            "risk_overview" -> 2
            "new_screening_button" -> 4
            else -> null
        }
        if (targetIndex != null) listState.animateScrollToItem(targetIndex)
    }

    // AppShell now draws the green grid backdrop once for every bottom-nav
    // tab, so this screen only needs its own scaffold padding, not a
    // second nested GridPatternBackground.
    LazyColumn(
        state = listState,
        modifier = Modifier
            .fillMaxSize()
            .padding(padding)
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        // The single most important action on this screen — a screening
        // request always starts here, so it's the first thing an officer
        // sees, not a button buried below five other cards.
        item {
            NewScreeningCta(onClick = onNewScreening, modifier = Modifier.tourAnchor("new_screening_button"))
        }

        item {
            // Plain rows, not a fixed-height lazy grid: the grid's 340dp cap
            // clipped the third row on phones and left the cards mostly empty.
            Column(modifier = Modifier.tourAnchor("stat_cards"), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                listOf(
                    StatCardData(stringResource(R.string.dashboard_total_screenings), stats.total, Icons.Filled.Description),
                    StatCardData(stringResource(R.string.dashboard_screenings_today), stats.today, Icons.Filled.Today, trendPct = stats.todayVsYesterdayPct),
                    StatCardData(stringResource(R.string.dashboard_high_risk_cases), stats.highRisk, Icons.Filled.Warning),
                    StatCardData(stringResource(R.string.dashboard_pending_reviews), stats.pending, Icons.Filled.PendingActions),
                    StatCardData(stringResource(R.string.dashboard_documents_scanned), stats.documentsScanned, Icons.Filled.CameraAlt),
                    StatCardData(stringResource(R.string.dashboard_needs_attention), alerts.size, Icons.Filled.NotificationsActive),
                ).chunked(2).forEach { pair ->
                    Row(horizontalArrangement = Arrangement.spacedBy(10.dp), modifier = Modifier.fillMaxWidth()) {
                        pair.forEach { data -> Box(Modifier.weight(1f)) { StatCard(data) } }
                    }
                }
            }
        }

        item {
            SectionCard(title = stringResource(R.string.dashboard_screening_activity)) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ChartRange.entries.forEach { range ->
                        FilterChip(
                            selected = chartRange == range,
                            onClick = { chartRange = range },
                            label = { Text(stringResource(range.labelRes)) },
                            colors = FilterChipDefaults.filterChipColors(
                                selectedContainerColor = AccentGreen.copy(alpha = 0.18f),
                                selectedLabelColor = AccentGreen,
                            ),
                            border = FilterChipDefaults.filterChipBorder(
                                enabled = true,
                                selected = chartRange == range,
                                borderColor = BorderDark,
                                selectedBorderColor = AccentGreen,
                            ),
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                MonoBarChart(
                    chartData,
                    // Hourly view opens on the current hour, not on 23:00 —
                    // the future — which would always read "0 screenings".
                    initialSelected = if (chartRange == ChartRange.TODAY) {
                        java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY)
                    } else {
                        chartData.lastIndex
                    },
                )
            }
        }

        item {
            SectionCard(title = stringResource(R.string.dashboard_risk_overview), modifier = Modifier.tourAnchor("risk_overview")) {
                Text(
                    stringResource(R.string.dashboard_total_risk_assessments, stats.total),
                    style = MaterialTheme.typography.bodySmall,
                    color = Gray600,
                )
                Spacer(Modifier.height(10.dp))
                MonoRibbonBar(stringResource(R.string.dashboard_low_risk), stats.lowRisk, stats.total, color = SuccessGreen)
                MonoRibbonBar(stringResource(R.string.dashboard_medium_risk), stats.mediumRisk, stats.total, color = WarningAmber)
                MonoRibbonBar(stringResource(R.string.dashboard_high_risk), stats.highRisk, stats.total, color = DestructiveRed)
            }
        }

        item {
            SectionCard(title = stringResource(R.string.dashboard_recent_screenings)) {
                if (items.isEmpty()) {
                    Text(stringResource(R.string.dashboard_no_screenings), style = MaterialTheme.typography.bodySmall, color = Gray600)
                } else {
                    items.take(5).forEach { item -> RecentRow(item, onClick = { onOpenScreening(item.id) }) }
                }
            }
        }

        item {
            SectionCard(title = stringResource(R.string.dashboard_more_section)) {
                QuickActionButton(stringResource(R.string.dashboard_view_queue), onViewQueue)
                Spacer(Modifier.height(8.dp))
                QuickActionButton(stringResource(R.string.dashboard_view_history), onViewHistory)
                Spacer(Modifier.height(8.dp))
                QuickActionButton(stringResource(R.string.dashboard_view_analytics), onViewAnalytics)
            }
        }
    }
}

private enum class ChartRange(val labelRes: Int) {
    TODAY(R.string.chart_today),
    WEEKLY(R.string.chart_weekly),
    MONTHLY(R.string.chart_monthly),
}

// Prominent, full-width CTA pinned at the very top of the dashboard — a
// screening always starts by picking a document type (see
// NewScreeningScreen), so this is the first thing an officer should see,
// not a button five cards down.
@Composable
private fun NewScreeningCta(onClick: () -> Unit, modifier: Modifier = Modifier) {
    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = AccentGreen),
        shape = RoundedCornerShape(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.AddCircle, contentDescription = null, tint = BackgroundDark, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(12.dp))
                Column {
                    Text(stringResource(R.string.dashboard_new_screening), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = BackgroundDark)
                    Text(stringResource(R.string.scan_document_prompt), style = MaterialTheme.typography.labelSmall, color = BackgroundDark.copy(alpha = 0.7f))
                }
            }
        }
    }
}

private data class StatCardData(val label: String, val value: Int, val icon: ImageVector, val trendPct: Int? = null)

@Composable
private fun StatCard(data: StatCardData) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = Gray100),
        border = androidx.compose.foundation.BorderStroke(1.dp, com.pramaanai.officer.ui.theme.BorderDark),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.Top) {
                Text(data.label, style = MaterialTheme.typography.labelMedium, color = Gray600, modifier = Modifier.weight(1f))
                Icon(data.icon, contentDescription = null, tint = Gray600, modifier = Modifier.size(16.dp))
            }
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
        colors = CardDefaults.cardColors(containerColor = CardDark),
        border = androidx.compose.foundation.BorderStroke(1.dp, BorderDark),
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
            val docLabel = item.documentType.replace("_", " ").replaceFirstChar { it.uppercase() }
            Text(
                "${item.nationality} · $docLabel · ${item.status.humanLabel()}",
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
