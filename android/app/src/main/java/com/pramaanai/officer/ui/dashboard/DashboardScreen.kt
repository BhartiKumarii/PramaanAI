package com.pramaanai.officer.ui.dashboard

import com.pramaanai.officer.R
import com.pramaanai.officer.ui.i18n.L
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.MarkEmailUnread
import androidx.compose.material.icons.filled.PendingActions
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.docverify.DocVerifyRepository
import com.pramaanai.officer.data.docverify.VerificationListItem
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.ChartBlue
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.MutedForeground
import com.pramaanai.officer.ui.theme.SecondaryDark
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import com.pramaanai.officer.ui.tour.tourAnchor
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Officer dashboard over the officer's own document verifications
 * (GET /api/v1/verification?mine=true). Every number is counted from real
 * records — nothing is estimated or hardcoded; an empty state says so. */
@Composable
fun DashboardScreen(
    @Suppress("UNUSED_PARAMETER") repository: ScreeningRepository,
    padding: PaddingValues,
    onVerifyDocument: () -> Unit,
    onOpenScreening: (String) -> Unit,
    onViewQueue: () -> Unit,
    onViewHistory: () -> Unit,
    onViewAnalytics: () -> Unit,
) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    var items by remember { mutableStateOf<List<VerificationListItem>?>(null) }
    var pending by remember { mutableIntStateOf(0) }
    var days by remember { mutableIntStateOf(7) }
    LaunchedEffect(Unit) {
        pending = repo.pendingCount()
        repo.listMine().onSuccess { items = it }.onFailure { if (items == null) items = emptyList() }
    }
    val all = items ?: emptyList()
    val zone = ZoneId.systemDefault()
    val today = LocalDate.now(zone)
    fun dateOf(it: VerificationListItem): LocalDate? = runCatching {
        val iso = it.createdAt!!
        Instant.parse(if (iso.endsWith("Z") || iso.contains('+')) iso else "${iso}Z").atZone(zone).toLocalDate()
    }.getOrNull()

    val listState = androidx.compose.foundation.lazy.rememberLazyListState()
    LaunchedEffect(com.pramaanai.officer.ui.tour.TourState.stepIndex, com.pramaanai.officer.ui.tour.TourState.active) {
        if (!com.pramaanai.officer.ui.tour.TourState.active) return@LaunchedEffect
        // LazyColumn item indices: 0 greeting, 1 verify CTA, 2 today tiles, 3 chart, 4 risk.
        val target = when (com.pramaanai.officer.ui.tour.TourState.currentStep?.anchorId) {
            "verify_document_button" -> 1
            "stat_cards" -> 2
            "activity_chart" -> 3
            "risk_overview" -> 4
            else -> null
        }
        if (target != null) listState.animateScrollToItem(target)
    }

    LazyColumn(Modifier.fillMaxSize().padding(padding), state = listState, contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item {
            val hour = java.time.LocalTime.now().hour
            Column {
                Text(com.pramaanai.officer.ui.i18n.L.f(if (hour < 12) com.pramaanai.officer.R.string.db_good_morning else if (hour < 17) com.pramaanai.officer.R.string.db_good_afternoon else com.pramaanai.officer.R.string.db_good_evening, AuthSession.username ?: "officer"),
                    style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(listOfNotNull(AuthSession.checkpointName?.let { L.f(R.string.db_post, it) },
                    today.format(DateTimeFormatter.ofPattern("EEEE, dd MMM"))).joinToString(" · "),
                    color = MutedForeground, style = MaterialTheme.typography.bodyMedium)
            }
        }
        item {
            com.pramaanai.officer.ui.docverify.VerifyDocumentCta(onClick = onVerifyDocument,
                modifier = Modifier.tourAnchor("verify_document_button"))
        }
        item {
            val todays = all.filter { dateOf(it) == today }
            Column(Modifier.tourAnchor("stat_cards"), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(L.s(R.string.db_today), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Kpi(L.s(R.string.db_checked_today), todays.size, L.f(R.string.db_passed_all_checks_count, todays.count { it.overallStatus == "PASS" }),
                        Icons.Filled.CheckCircle, AccentGreen, Modifier.weight(1f), onViewHistory)
                    Kpi(L.s(R.string.db_needs_your_decision), all.count { it.officerAction == "PENDING" && it.caseStatus in setOf("PENDING", "REVIEW_REQUIRED", null) },
                        L.s(R.string.db_across_all_days), Icons.Filled.PendingActions, WarningAmber, Modifier.weight(1f), onViewQueue)
                }
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Kpi(L.s(R.string.db_with_admin), all.count { it.caseStatus == "SENT" }, L.s(R.string.db_awaiting_a_response),
                        Icons.AutoMirrored.Filled.Send, ChartBlue, Modifier.weight(1f), onViewQueue)
                    Kpi(L.s(R.string.db_admin_responded), all.count { it.reviewerResponded == true }, L.s(R.string.db_open_to_read),
                        Icons.Filled.MarkEmailUnread, SuccessGreen, Modifier.weight(1f), onViewQueue)
                }
            }
        }
        item {
            Panel("Activity", Modifier.tourAnchor("activity_chart")) {
                val chipColors = FilterChipDefaults.filterChipColors(selectedContainerColor = AccentGreen, selectedLabelColor = BackgroundDark)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(7 to L.s(R.string.db_7_days), 30 to L.s(R.string.db_30_days)).forEach { (d, l) ->
                        FilterChip(selected = days == d, onClick = { days = d }, label = { Text(l) }, colors = chipColors)
                    }
                }
                Spacer(Modifier.height(8.dp))
                val range = (days - 1 downTo 0).map { today.minusDays(it.toLong()) }
                val byDay = all.groupBy { dateOf(it) }
                val bars = range.map { d ->
                    val rows = byDay[d] ?: emptyList()
                    Bar(d, rows.count { it.overallStatus == "PASS" },
                        rows.count { it.overallStatus in setOf("REVIEW_REQUIRED", "FAIL") },
                        rows.count { it.overallStatus !in setOf("PASS", "REVIEW_REQUIRED", "FAIL") })
                }
                StackedChart(bars)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                    Legend(L.s(R.string.db_verified), SuccessGreen); Legend(L.s(R.string.db_needs_attention), WarningAmber); Legend(L.s(R.string.db_not_verified), MutedForeground)
                }
            }
        }
        item {
            Panel("Risk distribution", Modifier.tourAnchor("risk_overview")) {
                val high = all.count { it.riskLevel == "HIGH" }
                val med = all.count { it.riskLevel == "MEDIUM" }
                val low = all.count { it.riskLevel == "LOW" || it.riskLevel == null }
                val total = (high + med + low).coerceAtLeast(1)
                Row(Modifier.fillMaxWidth().height(14.dp).background(SecondaryDark, RoundedCornerShape(7.dp))) {
                    listOf(high to DestructiveRed, med to WarningAmber, low to SuccessGreen).forEach { (n, c) ->
                        if (n > 0) Box(Modifier.weight(n.toFloat() / total).fillMaxWidth().height(14.dp).background(c, RoundedCornerShape(7.dp)))
                    }
                }
                Spacer(Modifier.height(10.dp))
                listOf(Triple(L.s(R.string.db_high_risk), high, DestructiveRed), Triple(L.s(R.string.db_medium_risk), med, WarningAmber),
                    Triple(L.s(R.string.db_low_risk), low, SuccessGreen)).forEach { (l, n, c) ->
                    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(10.dp).background(c, CircleShape))
                        Spacer(Modifier.width(8.dp))
                        Text(l, modifier = Modifier.weight(1f))
                        Text("$n", fontWeight = FontWeight.Bold, color = c)
                        Text("  ${(n * 100 / total)}%", color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                    }
                }
                Text(L.s(R.string.db_a_risk_indicator_explains_which),
                    color = MutedForeground, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
            }
        }
        if (pending > 0) item {
            Card(colors = CardDefaults.cardColors(containerColor = ChartBlue.copy(alpha = 0.12f)),
                border = BorderStroke(1.dp, ChartBlue.copy(alpha = 0.45f)), shape = RoundedCornerShape(12.dp)) {
                Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.CloudOff, null, tint = ChartBlue)
                    Spacer(Modifier.width(10.dp))
                    Text(L.f(R.string.db_verification_s_saved_offline_sent, pending))
                }
            }
        }
        item {
            Panel(L.s(R.string.db_recent_verifications)) {
                if (items == null) Text(L.s(R.string.db_loading), color = MutedForeground)
                else if (all.isEmpty()) Text(L.s(R.string.db_no_verifications_yet_tap_verify), color = MutedForeground)
                all.take(5).forEach { v -> RecentRow(v) { onOpenScreening(v.id) } }
                if (all.size > 5) TextButton(onClick = onViewHistory) {
                    Text(L.s(R.string.db_see_all_in_history), color = AccentGreen)
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = AccentGreen)
                }
            }
        }
        item {
            TextButton(onClick = onViewAnalytics) { Text(L.s(R.string.db_open_analytics), color = MutedForeground) }
        }
    }
}

private data class Bar(val day: LocalDate, val ok: Int, val attention: Int, val notVerified: Int) {
    val total get() = ok + attention + notVerified
}

@Composable
private fun StackedChart(bars: List<Bar>) {
    var selected by remember(bars.size) { mutableIntStateOf(bars.lastIndex) }
    val top = (bars.maxOfOrNull { it.total } ?: 0).coerceAtLeast(1)
    val sel = bars.getOrNull(selected)
    sel?.let {
        Text(L.f(R.string.db_day_summary, it.day.format(DateTimeFormatter.ofPattern("EEE, dd MMM")), it.total, it.ok,
            it.attention, it.notVerified), color = MutedForeground, style = MaterialTheme.typography.bodySmall)
    }
    Spacer(Modifier.height(6.dp))
    Canvas(Modifier.fillMaxWidth().height(150.dp).pointerInput(bars) {
        detectTapGestures { pos -> selected = (pos.x / (size.width / bars.size)).toInt().coerceIn(0, bars.lastIndex) }
    }) {
        val slot = size.width / bars.size
        val barW = (slot * 0.62f).coerceAtMost(28.dp.toPx())
        bars.forEachIndexed { i, b ->
            val x = i * slot + (slot - barW) / 2
            var y = size.height
            listOf(b.ok to SuccessGreen, b.attention to WarningAmber, b.notVerified to MutedForeground).forEach { (n, c) ->
                if (n > 0) {
                    val h = size.height * n / top
                    drawRoundRect(if (i == selected) c else c.copy(alpha = 0.55f), topLeft = Offset(x, y - h), size = Size(barW, h),
                        cornerRadius = CornerRadius(4f))
                    y -= h
                }
            }
            if (b.total == 0) drawRoundRect(SecondaryDark, topLeft = Offset(x, size.height - 4f), size = Size(barW, 4f))
        }
    }
    Row(Modifier.fillMaxWidth()) {
        val step = if (bars.size > 7) bars.size / 6 else 1
        bars.forEachIndexed { i, b ->
            Text(if (i % step == 0) b.day.format(DateTimeFormatter.ofPattern(if (bars.size > 7) "dd" else "EEE")) else "",
                color = if (i == selected) AccentGreen else MutedForeground, style = MaterialTheme.typography.labelSmall,
                modifier = Modifier.weight(1f), maxLines = 1)
        }
    }
}

@Composable
private fun Legend(label: String, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(color, RoundedCornerShape(3.dp)))
        Spacer(Modifier.width(5.dp))
        Text(label, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun Kpi(label: String, value: Int, sub: String, icon: ImageVector, color: Color, modifier: Modifier, onClick: () -> Unit) {
    Card(onClick = onClick, modifier = modifier, colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(30.dp).background(color.copy(alpha = 0.15f), RoundedCornerShape(8.dp)), contentAlignment = Alignment.Center) {
                    Icon(icon, contentDescription = null, tint = color, modifier = Modifier.size(18.dp))
                }
                Spacer(Modifier.width(8.dp))
                Text(label, color = MutedForeground, style = MaterialTheme.typography.labelMedium, maxLines = 2)
            }
            Spacer(Modifier.height(8.dp))
            Text("$value", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text(sub, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun Panel(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Card(modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

@Composable
private fun RecentRow(item: VerificationListItem, onClick: () -> Unit) {
    val (label, color) = when (item.overallStatus) {
        "PASS" -> L.s(R.string.db_verified_2) to SuccessGreen
        "REVIEW_REQUIRED" -> L.s(R.string.db_review_required) to WarningAmber
        "FAIL" -> L.s(R.string.db_check_failed) to DestructiveRed
        "OFFICIAL_VERIFICATION_REQUIRED", "REGISTRY_NOT_AVAILABLE" -> L.s(R.string.db_official_check_needed) to ChartBlue
        else -> L.s(R.string.db_not_verified_2) to MutedForeground
    }
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(color, CircleShape))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(item.documentTypes?.joinToString(" + ") { it.replace('_', ' ').lowercase().replaceFirstChar { c -> c.uppercase() } } ?: L.s(R.string.db_document),
                fontWeight = FontWeight.Medium)
            Text(listOfNotNull(item.caseNumber, item.country?.lowercase()?.replaceFirstChar { it.uppercase() }).joinToString(" · "),
                color = MutedForeground, style = MaterialTheme.typography.bodySmall)
        }
        Text(label, color = color, style = MaterialTheme.typography.labelMedium)
    }
}
