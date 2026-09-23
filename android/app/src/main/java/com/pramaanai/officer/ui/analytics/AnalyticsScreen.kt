package com.pramaanai.officer.ui.analytics

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.docverify.DocVerifyRepository
import com.pramaanai.officer.data.docverify.VerificationListItem
import com.pramaanai.officer.ui.docverify.checkTitle
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.ChartBlue
import com.pramaanai.officer.ui.theme.ChartPurple
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.MutedForeground
import com.pramaanai.officer.ui.theme.SecondaryDark
import com.pramaanai.officer.ui.theme.SidebarDark
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import java.time.Instant
import java.time.ZoneId

/** Analytics over the officer's own verifications. Every figure is counted
 * from stored records for the chosen period; nothing is projected. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AnalyticsScreen(@Suppress("UNUSED_PARAMETER") repository: ScreeningRepository, onBack: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    var items by remember { mutableStateOf<List<VerificationListItem>?>(null) }
    var failed by remember { mutableStateOf(false) }
    var days by remember { mutableIntStateOf(30) }
    LaunchedEffect(Unit) { repo.listMine().fold({ items = it }, { failed = true }) }

    fun instant(i: VerificationListItem): Instant? = runCatching {
        val iso = i.createdAt!!
        Instant.parse(if (iso.endsWith("Z") || iso.contains('+')) iso else "${iso}Z")
    }.getOrNull()
    val cutoff = Instant.now().minusSeconds(days * 86_400L)
    val data = (items ?: emptyList()).filter { instant(it)?.isAfter(cutoff) == true }

    Scaffold(topBar = {
        TopAppBar(title = { Text("Analytics", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = SidebarDark))
    }) { padding ->
        if (items == null) {
            Box(Modifier.fillMaxSize().padding(padding), contentAlignment = Alignment.Center) {
                if (failed) Text("Could not load — check the connection.", color = MutedForeground)
                else CircularProgressIndicator(color = AccentGreen)
            }
            return@Scaffold
        }
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                val chipColors = FilterChipDefaults.filterChipColors(selectedContainerColor = AccentGreen, selectedLabelColor = BackgroundDark)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(7 to "7 days", 30 to "30 days", 90 to "90 days").forEach { (d, l) ->
                        FilterChip(selected = days == d, onClick = { days = d }, label = { Text(l) }, colors = chipColors)
                    }
                }
                Text("Your verifications in the last $days days", color = MutedForeground, style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 4.dp))
            }
            if (data.isEmpty()) {
                item { Text("No verifications in this period.", color = MutedForeground) }
                return@LazyColumn
            }
            val total = data.size
            fun pct(n: Int) = if (total == 0) 0 else n * 100 / total
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Stat("Checked", "$total", "documents", AccentGreen, Modifier.weight(1f))
                    Stat("Passed all checks", "${pct(data.count { it.overallStatus == "PASS" })}%", "of checked", SuccessGreen, Modifier.weight(1f))
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Stat("Average risk", "${data.mapNotNull { it.riskScore }.average().let { if (it.isNaN()) 0 else it.toInt() }}/100",
                        "indicator, not a verdict", WarningAmber, Modifier.weight(1f))
                    Stat("Sent to admin", "${pct(data.count { it.caseStatus == "SENT" || it.reviewerResponded == true })}%",
                        "${data.count { it.reviewerResponded == true }} answered", ChartBlue, Modifier.weight(1f))
                }
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Stat("Captured offline", "${data.count { it.capturedOffline == true }}", "synced later", ChartPurple, Modifier.weight(1f))
                    Stat("High risk", "${data.count { it.riskLevel == "HIGH" }}", "need close review", DestructiveRed, Modifier.weight(1f))
                }
            }
            item {
                Panel("Results") {
                    Bars(listOf(
                        Triple("Verified", data.count { it.overallStatus == "PASS" }, SuccessGreen),
                        Triple("Review required", data.count { it.overallStatus == "REVIEW_REQUIRED" }, WarningAmber),
                        Triple("Check failed", data.count { it.overallStatus == "FAIL" }, DestructiveRed),
                        Triple("Official / registry check needed", data.count { it.overallStatus in setOf("OFFICIAL_VERIFICATION_REQUIRED", "REGISTRY_NOT_AVAILABLE") }, ChartBlue),
                        Triple("Not verified", data.count { it.overallStatus == "NOT_VERIFIED" }, MutedForeground),
                    ), total)
                }
            }
            item {
                Panel("Most common reasons for attention") {
                    val reasons = data.flatMap { it.attentionChecks ?: emptyList() }.groupingBy { it }.eachCount()
                        .entries.sortedByDescending { it.value }.take(8)
                    if (reasons.isEmpty()) Text("No check needed attention in this period.", color = MutedForeground)
                    else Bars(reasons.map { Triple(checkTitle(it.key), it.value, WarningAmber) }, total)
                    Text("Share of checked documents where the check needed the officer's attention.", color = MutedForeground,
                        style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(top = 6.dp))
                }
            }
            item {
                Panel("By document type") {
                    Bars(data.groupingBy { human(it.documentTypes?.firstOrNull() ?: "Unknown") }.eachCount().entries
                        .sortedByDescending { it.value }.map { Triple(it.key, it.value, AccentGreen) }, total)
                }
            }
            item {
                Panel("By country of document") {
                    Bars(data.groupingBy { human(it.country ?: "Not identified") }.eachCount().entries
                        .sortedByDescending { it.value }.map { Triple(it.key, it.value, ChartBlue) }, total)
                }
            }
            item {
                Panel("Time of day") {
                    val zone = ZoneId.systemDefault()
                    val slots = listOf("00–06" to 0..5, "06–12" to 6..11, "12–18" to 12..17, "18–24" to 18..23)
                    Bars(slots.map { (label, hours) ->
                        Triple(label, data.count { instant(it)?.atZone(zone)?.hour in hours }, ChartPurple)
                    }, total)
                }
            }
        }
    }
}

private fun human(s: String) = s.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }

@Composable
private fun Stat(label: String, value: String, sub: String, color: Color, modifier: Modifier) {
    Card(modifier, colors = CardDefaults.cardColors(containerColor = CardDark), border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(14.dp)) {
            Text(label, color = MutedForeground, style = MaterialTheme.typography.labelMedium)
            Text(value, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = color)
            Text(sub, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun Panel(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(10.dp))
            content()
        }
    }
}

/** Horizontal bars: label, count, share of [total]. */
@Composable
private fun Bars(rows: List<Triple<String, Int, Color>>, total: Int) {
    val max = (rows.maxOfOrNull { it.second } ?: 0).coerceAtLeast(1)
    rows.forEach { (label, n, color) ->
        Column(Modifier.padding(vertical = 4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
                Text("$n", fontWeight = FontWeight.Bold)
                Text("  ${if (total == 0) 0 else n * 100 / total}%", color = MutedForeground, style = MaterialTheme.typography.labelSmall,
                    modifier = Modifier.width(44.dp))
            }
            Box(Modifier.fillMaxWidth().height(8.dp).background(SecondaryDark, RoundedCornerShape(4.dp))) {
                if (n > 0) Box(Modifier.fillMaxWidth(n.toFloat() / max).height(8.dp).background(color, RoundedCornerShape(4.dp)))
            }
        }
    }
    if (rows.isEmpty()) Text("No data.", color = MutedForeground)
    Spacer(Modifier.size(2.dp))
}
