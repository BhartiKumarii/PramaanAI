package com.pramaanai.officer.ui.verifications

import android.content.Context
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.CloudOff
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.MarkEmailUnread
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.data.docverify.DocVerifyRepository
import com.pramaanai.officer.data.docverify.VerificationListItem
import com.pramaanai.officer.data.docverify.VerificationOutcome
import com.pramaanai.officer.ui.docverify.DocVerifyResultView
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.ChartBlue
import com.pramaanai.officer.ui.theme.DestructiveRed
import com.pramaanai.officer.ui.theme.MutedForeground
import com.pramaanai.officer.ui.theme.SidebarDark
import com.pramaanai.officer.ui.theme.SuccessGreen
import com.pramaanai.officer.ui.theme.WarningAmber
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Review / History / Notifications over the officer's own verifications
 * (GET /api/v1/verification?mine=true — summary only, no personal fields;
 * the full result, including a reviewing officer's written response, is
 * loaded only when one is opened). */
enum class ListMode { REVIEW, HISTORY, NOTIFICATIONS }

/** Which reviewing-officer responses this phone has already shown. */
object ResponseTracker {
    private const val PREFS = "pramaan_seen_responses"
    private fun key(item: VerificationListItem) = "${item.id}:${item.caseStatus}:${item.lastUpdateAt}"
    fun isNew(context: Context, item: VerificationListItem): Boolean =
        item.reviewerResponded == true &&
            !context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getBoolean(key(item), false)
    fun markSeen(context: Context, item: VerificationListItem) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putBoolean(key(item), true).apply()
    fun unseenCount(context: Context, items: List<VerificationListItem>) = items.count { isNew(context, it) }
}

private data class Stage(val label: String, val color: Color, val icon: ImageVector)

private fun stageOf(item: VerificationListItem): Stage = when {
    item.caseStatus == "SENT" -> Stage("Sent — awaiting admin", ChartBlue, Icons.AutoMirrored.Filled.Send)
    item.reviewerResponded == true -> Stage("Admin responded: ${com.pramaanai.officer.ui.docverify.caseStatusLabel(item.caseStatus)}",
        if (item.caseStatus == "CLEAR") SuccessGreen else WarningAmber, Icons.Filled.MarkEmailUnread)
    item.caseStatus == "CLEAR" || item.officerAction == "CLEARED" -> Stage("Cleared by you", SuccessGreen, Icons.Filled.CheckCircle)
    item.caseStatus in setOf("SECONDARY_REVIEW", "HOLD_REFER") -> Stage(com.pramaanai.officer.ui.docverify.caseStatusLabel(item.caseStatus), WarningAmber, Icons.Filled.Warning)
    else -> Stage("Needs your decision", AccentGreen, Icons.Filled.Info)
}

private fun resultUi(status: String): Pair<String, Color> = when (status) {
    "PASS" -> "Verified" to SuccessGreen
    "REVIEW_REQUIRED" -> "Review required" to WarningAmber
    "FAIL" -> "Check failed" to DestructiveRed
    "REGISTRY_NOT_AVAILABLE" -> "Registry not available" to ChartBlue
    "OFFICIAL_VERIFICATION_REQUIRED" -> "Official verification required" to ChartBlue
    else -> "Not verified" to MutedForeground
}

private fun humanize(s: String) = s.replace('_', ' ').lowercase().replaceFirstChar { it.uppercase() }

private val TIME = DateTimeFormatter.ofPattern("dd MMM, HH:mm").withZone(ZoneId.systemDefault())
private fun time(iso: String?): String = runCatching { TIME.format(Instant.parse(if (iso!!.endsWith("Z") || iso.contains('+')) iso else "${iso}Z")) }
    .getOrDefault(iso ?: "")

/** Filters shared by Review and History (all optional; null = any). */
private data class Filters(val result: String? = null, val risk: String? = null, val doc: String? = null,
                           val periodDays: Int? = null) {
    val active get() = listOf(result, risk, doc, periodDays).count { it != null }
}

private val DOC_GROUPS = listOf(
    "PASSPORT" to "Passport", "VISA" to "Visa", "DRIVING_LICENCE" to "Driving licence",
    "AADHAAR" to "Aadhaar", "PERMIT" to "Permit", "STAMP" to "Stamp page", "OTHER" to "Other",
)

private fun docGroup(types: List<String>?): String {
    val t = types?.firstOrNull() ?: return "OTHER"
    return when {
        "PASSPORT" in t -> "PASSPORT"
        "VISA" in t -> "VISA"
        t == "DRIVING_LICENCE" -> "DRIVING_LICENCE"
        t == "AADHAAR" -> "AADHAAR"
        "PERMIT" in t -> "PERMIT"
        t == "IMMIGRATION_STAMP" -> "STAMP"
        else -> "OTHER"
    }
}

private fun Filters.matches(item: VerificationListItem): Boolean {
    val resultOk = when (result) {
        null -> true
        "VERIFIED" -> item.overallStatus == "PASS"
        "ATTENTION" -> item.overallStatus in setOf("FAIL", "REVIEW_REQUIRED")
        else -> item.overallStatus !in setOf("PASS", "FAIL", "REVIEW_REQUIRED")
    }
    val riskOk = risk == null || (item.riskLevel ?: "LOW") == risk
    val docOk = doc == null || docGroup(item.documentTypes) == doc
    val periodOk = periodDays == null || runCatching {
        val iso = item.createdAt!!
        val t = Instant.parse(if (iso.endsWith("Z") || iso.contains('+')) iso else "${iso}Z")
        t.isAfter(Instant.now().minusSeconds((periodDays ?: 0) * 86_400L))
    }.getOrDefault(true)
    return resultOk && riskOk && docOk && periodOk
}

@Composable
private fun FilterBar(filters: Filters, showPeriod: Boolean, shown: Int, total: Int, onChange: (Filters) -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = CardDark), border = BorderStroke(1.dp, BorderDark),
        shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.FilterList, contentDescription = null, tint = AccentGreen, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Filter by", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Text("$shown of $total", color = MutedForeground, style = MaterialTheme.typography.labelMedium)
                if (filters.active > 0) androidx.compose.material3.TextButton(onClick = { onChange(Filters()) }) {
                    Text("Clear", color = AccentGreen)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Dropdown("Result", filters.result, listOf("VERIFIED" to "Verified", "ATTENTION" to "Needs attention",
                    "NOT_VERIFIED" to "Not verified"), Modifier.weight(1f)) { onChange(filters.copy(result = it)) }
                Dropdown("Risk", filters.risk, listOf("HIGH" to "High", "MEDIUM" to "Medium", "LOW" to "Low"),
                    Modifier.weight(1f)) { onChange(filters.copy(risk = it)) }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Dropdown("Document", filters.doc, DOC_GROUPS, Modifier.weight(1f)) { onChange(filters.copy(doc = it)) }
                if (showPeriod) Dropdown("Period", filters.periodDays, listOf(1 to "Today", 7 to "Last 7 days", 30 to "Last 30 days"),
                    Modifier.weight(1f)) { onChange(filters.copy(periodDays = it)) }
            }
        }
    }
}

/** One "filter by" field: shows its current choice (or "Any") and opens a menu. */
@Composable
private fun <T> Dropdown(label: String, selected: T?, options: List<Pair<T, String>>, modifier: Modifier, onPick: (T?) -> Unit) {
    var open by remember { mutableStateOf(false) }
    val current = options.firstOrNull { it.first == selected }?.second
    Box(modifier) {
        androidx.compose.material3.OutlinedButton(onClick = { open = true }, modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(10.dp),
            border = BorderStroke(1.dp, if (current != null) AccentGreen else BorderDark),
            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 8.dp)) {
            Column(Modifier.weight(1f)) {
                Text(label, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                Text(current ?: "Any", color = if (current != null) AccentGreen else MaterialTheme.colorScheme.onSurface,
                    fontWeight = FontWeight.SemiBold, maxLines = 1)
            }
            Icon(Icons.Filled.ArrowDropDown, contentDescription = "Choose $label", tint = MutedForeground)
        }
        androidx.compose.material3.DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            androidx.compose.material3.DropdownMenuItem(text = { Text("Any") }, onClick = { onPick(null); open = false })
            options.forEach { (v, l) ->
                androidx.compose.material3.DropdownMenuItem(
                    text = { Text(l, fontWeight = if (v == selected) FontWeight.Bold else FontWeight.Normal,
                        color = if (v == selected) AccentGreen else MaterialTheme.colorScheme.onSurface) },
                    onClick = { onPick(v); open = false })
            }
        }
    }
}

@Composable
fun VerificationListScreen(padding: PaddingValues, mode: ListMode, onOpen: (String) -> Unit) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<VerificationListItem>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var pending by remember { mutableIntStateOf(0) }
    var filters by remember { mutableStateOf(Filters()) }
    var query by remember { mutableStateOf("") }

    fun load() = scope.launch {
        pending = repo.pendingCount()
        repo.listMine().fold({ items = it; error = null }, { error = "Could not load — check the connection, then tap Refresh." })
    }
    LaunchedEffect(Unit) { load() }
    val everything = items ?: emptyList()
    val all = if (mode == ListMode.NOTIFICATIONS) everything else everything.filter { filters.matches(it) }
    val open: (VerificationListItem) -> Unit = { ResponseTracker.markSeen(context, it); onOpen(it.id) }

    LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(when (mode) {
                        ListMode.REVIEW -> "Waiting on you or the admin"
                        ListMode.HISTORY -> "Verification history"
                        ListMode.NOTIFICATIONS -> "Admin responses and risk alerts"
                    }, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    Text(when (mode) {
                        ListMode.REVIEW -> "Decide, or follow what you sent to the admin"
                        ListMode.HISTORY -> "Everything you verified, newest first"
                        ListMode.NOTIFICATIONS -> "New responses first, then results by risk level"
                    }, color = MutedForeground, style = MaterialTheme.typography.bodySmall)
                }
                IconButton(onClick = { load() }) { Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = AccentGreen) }
            }
        }
        if (pending > 0) item {
            Banner("$pending verification(s) saved offline", "Encrypted on this phone. Sent automatically when the connection returns.",
                ChartBlue, Icons.Filled.CloudOff)
        }
        when {
            items == null && error == null -> item {
                Box(Modifier.fillMaxWidth().padding(32.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = AccentGreen) }
            }
            error != null && items == null -> item { Banner("Not loaded", error!!, WarningAmber, Icons.Filled.Warning) }
            else -> when (mode) {
                ListMode.REVIEW -> {
                    val decide = all.filter { stageOf(it).label.startsWith("Needs") }
                    val sent = all.filter { it.caseStatus == "SENT" }
                    val responded = all.filter { it.reviewerResponded == true }
                    item { SummaryRow(listOf(Triple("Needs decision", decide.size, AccentGreen),
                        Triple("With admin", sent.size, ChartBlue), Triple("Admin responded", responded.size, WarningAmber))) }
                    item { FilterBar(filters, showPeriod = false, shown = decide.size + sent.size + responded.size,
                        total = everything.count { stageOf(it).label.startsWith("Needs") || it.caseStatus == "SENT" || it.reviewerResponded == true }) { filters = it } }
                    if (decide.isEmpty() && sent.isEmpty() && responded.isEmpty()) item {
                        EmptyText("Nothing waiting. Cleared verifications are in History.")
                    }
                    section(this, "Needs your decision", decide, AccentGreen) { ReviewCard(it, ResponseTracker.isNew(context, it)) { open(it) } }
                    section(this, "Sent — awaiting admin", sent, ChartBlue) { ReviewCard(it, false) { open(it) } }
                    section(this, "Admin responded", responded.sortedByDescending { ResponseTracker.isNew(context, it) }, WarningAmber) {
                        ReviewCard(it, ResponseTracker.isNew(context, it)) { open(it) }
                    }
                }
                ListMode.HISTORY -> {
                    item {
                        OutlinedTextField(value = query, onValueChange = { query = it }, modifier = Modifier.fillMaxWidth(),
                            leadingIcon = { Icon(Icons.Filled.Search, null) }, singleLine = true,
                            placeholder = { Text("Search case number, country, document") })
                    }
                    val filtered = all.filter { item ->
                        query.isBlank() || listOfNotNull(item.caseNumber, item.country, item.documentTypes?.joinToString())
                            .any { it.contains(query.trim(), ignoreCase = true) }
                    }
                    item { FilterBar(filters, showPeriod = true, shown = filtered.size, total = everything.size) { filters = it } }
                    if (filtered.isEmpty()) item { EmptyText("No verifications match.") }
                    filtered.groupBy { day(it.createdAt) }.forEach { (d, rows) ->
                        item(key = "h-$d") {
                            Text("$d · ${rows.size}", color = MutedForeground, style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 8.dp))
                        }
                        items(rows, key = { it.id }) { HistoryRow(it) { open(it) } }
                    }
                }
                ListMode.NOTIFICATIONS -> {
                    val responses = all.filter { it.reviewerResponded == true }.sortedByDescending { ResponseTracker.isNew(context, it) }
                    val levels = com.pramaanai.officer.data.local.AppSettings.alertLevels(context)
                    val byLevel = all.filter { it.reviewerResponded != true && (it.riskLevel ?: "LOW") in levels }
                        .groupBy { it.riskLevel ?: "LOW" }
                    item { SummaryRow(listOf(Triple("High risk", byLevel["HIGH"]?.size ?: 0, DestructiveRed),
                        Triple("Medium risk", byLevel["MEDIUM"]?.size ?: 0, WarningAmber),
                        Triple("Low risk", byLevel["LOW"]?.size ?: 0, SuccessGreen))) }
                    section(this, "Admin responses", responses, WarningAmber) { ReviewCard(it, ResponseTracker.isNew(context, it)) { open(it) } }
                    section(this, "High risk", byLevel["HIGH"] ?: emptyList(), DestructiveRed) { ReviewCard(it, false) { open(it) } }
                    section(this, "Medium risk", byLevel["MEDIUM"] ?: emptyList(), WarningAmber) { ReviewCard(it, false) { open(it) } }
                    section(this, "Low risk", (byLevel["LOW"] ?: emptyList()).take(10), SuccessGreen) { HistoryRow(it) { open(it) } }
                    if (all.isEmpty()) item { EmptyText("No notifications yet.") }
                }
            }
        }
    }
}

private fun section(scope: androidx.compose.foundation.lazy.LazyListScope, title: String, rows: List<VerificationListItem>,
                    color: Color, row: @Composable (VerificationListItem) -> Unit) {
    if (rows.isEmpty()) return
    scope.item(key = "s-$title") {
        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
            Box(Modifier.size(10.dp).background(color, CircleShape))
            Spacer(Modifier.width(8.dp))
            Text("$title (${rows.size})", fontWeight = FontWeight.SemiBold, color = color)
        }
    }
    scope.items(rows, key = { "$title-${it.id}" }) { row(it) }
}

@Composable
private fun EmptyText(text: String) = Text(text, color = MutedForeground, modifier = Modifier.padding(vertical = 24.dp))

private val DAY = DateTimeFormatter.ofPattern("EEE, dd MMM").withZone(ZoneId.systemDefault())
private fun day(iso: String?): String = runCatching {
    val instant = Instant.parse(if (iso!!.endsWith("Z") || iso.contains('+')) iso else "${iso}Z")
    val d = instant.atZone(ZoneId.systemDefault()).toLocalDate()
    val today = java.time.LocalDate.now()
    when (d) { today -> "Today"; today.minusDays(1) -> "Yesterday"; else -> DAY.format(instant) }
}.getOrDefault("Earlier")

@Composable
private fun HistoryRow(item: VerificationListItem, onClick: () -> Unit) {
    val (resultLabel, resultColor) = resultUi(item.overallStatus)
    Row(Modifier.fillMaxWidth().background(CardDark, RoundedCornerShape(10.dp))
        .then(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)).clickableRow(onClick),
        verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(resultColor, CircleShape))
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(item.documentTypes?.joinToString(" + ") { humanize(it) } ?: "Document", fontWeight = FontWeight.Medium)
            Text(listOfNotNull(time(item.createdAt).substringAfter(", ", ""), item.caseNumber, item.country?.let { humanize(it) })
                .filter { it.isNotBlank() }.joinToString(" · "), color = MutedForeground, style = MaterialTheme.typography.bodySmall)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(resultLabel, color = resultColor, style = MaterialTheme.typography.labelSmall)
            Text(stageOf(item).label.substringBefore(":"), color = MutedForeground, style = MaterialTheme.typography.labelSmall)
        }
    }
}

private fun Modifier.clickableRow(onClick: () -> Unit) = this.then(Modifier.clickable(onClick = onClick))

@Composable
private fun SummaryRow(tiles: List<Triple<String, Int, Color>>) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        tiles.forEach { (label, n, color) ->
            Card(Modifier.weight(1f), colors = CardDefaults.cardColors(containerColor = CardDark), border = BorderStroke(1.dp, BorderDark),
                shape = RoundedCornerShape(12.dp)) {
                Column(Modifier.padding(12.dp)) {
                    Text("$n", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = color)
                    Text(label, color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}

@Composable
private fun ReviewCard(item: VerificationListItem, isNew: Boolean, onClick: () -> Unit) {
    val stage = stageOf(item)
    val (resultLabel, resultColor) = resultUi(item.overallStatus)
    Card(onClick = onClick, colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(if (isNew) 2.dp else 1.dp, if (isNew) WarningAmber else BorderDark), shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.fillMaxWidth().padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.documentTypes?.joinToString(" + ") { humanize(it) } ?: "Document", fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f))
                if (isNew) Box(Modifier.background(WarningAmber, RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 2.dp)) {
                    Text("NEW", color = BackgroundDark, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
                }
            }
            Text(listOfNotNull(item.caseNumber, item.country?.let { humanize(it) }, time(item.createdAt)).joinToString(" · "),
                color = MutedForeground, style = MaterialTheme.typography.bodySmall)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).background(resultColor, CircleShape))
                Spacer(Modifier.width(6.dp))
                Text(resultLabel, color = resultColor, style = MaterialTheme.typography.labelMedium)
                item.riskScore?.let { Text("  ·  risk $it/100", color = MutedForeground, style = MaterialTheme.typography.labelMedium) }
            }
            Spacer(Modifier.height(4.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(stage.icon, contentDescription = null, tint = stage.color, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp))
                Text(stage.label, color = stage.color, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

@Composable
private fun Banner(title: String, body: String, color: Color, icon: ImageVector) {
    Card(colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.12f)),
        border = BorderStroke(1.dp, color.copy(alpha = 0.45f)), shape = RoundedCornerShape(12.dp)) {
        Row(Modifier.fillMaxWidth().padding(14.dp)) {
            Icon(icon, contentDescription = null, tint = color)
            Spacer(Modifier.width(10.dp))
            Column {
                Text(title, color = color, fontWeight = FontWeight.Bold)
                Text(body, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

/** Full-screen detail of one verification (from Review / History / Notifications). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VerificationDetailScreen(verificationId: String, onBack: () -> Unit) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    var outcome by remember { mutableStateOf<VerificationOutcome?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(verificationId) {
        repo.load(verificationId).fold({ outcome = it }, { error = "Could not load this verification — check the connection." })
    }
    Scaffold(topBar = {
        TopAppBar(title = { Text("Verification", fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back") } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = SidebarDark))
    }) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            val o = outcome
            when {
                o != null -> DocVerifyResultView(o, bitmap = null, repo = repo)
                error != null -> Box(Modifier.padding(16.dp)) { Banner("Not loaded", error!!, WarningAmber, Icons.Filled.Error) }
                else -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = AccentGreen) }
            }
        }
    }
}
