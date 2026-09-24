package com.pramaanai.officer.ui.profile

import com.pramaanai.officer.R
import com.pramaanai.officer.ui.i18n.L
import android.os.Build
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.BuildConfig
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.connectivity.ConnectivityMonitor
import com.pramaanai.officer.data.docverify.CaptureStore
import com.pramaanai.officer.data.docverify.DocVerifyRepository
import com.pramaanai.officer.data.docverify.VerificationListItem
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.ui.components.OfficerAvatar
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

/** The signed-in officer: who and where they are, their own work in numbers,
 * this device and its connection, the data kept on this phone, and account
 * actions. Every figure comes from the officer's stored verifications. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfficerProfileScreen(
    @Suppress("UNUSED_PARAMETER") repository: ScreeningRepository,
    onBack: () -> Unit,
    onLogout: () -> Unit,
    onOpenSettings: () -> Unit,
    onReplayTour: () -> Unit = {},
) {
    val context = LocalContext.current
    val repo = remember { DocVerifyRepository(context.applicationContext) }
    val scope = rememberCoroutineScope()
    var items by remember { mutableStateOf<List<VerificationListItem>>(emptyList()) }
    var stored by remember { mutableIntStateOf(0) }
    var pending by remember { mutableIntStateOf(0) }
    var period by remember { mutableIntStateOf(7) }
    var confirmClear by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        repo.listMine().onSuccess { items = it }
        stored = CaptureStore.get(context).count()
        pending = repo.pendingCount()
    }
    val cutoff = if (period == 0) Instant.EPOCH else Instant.now().minusSeconds(period * 86_400L)
    val inPeriod = items.filter {
        runCatching {
            val iso = it.createdAt!!
            Instant.parse(if (iso.endsWith("Z") || iso.contains('+')) iso else "${iso}Z").isAfter(cutoff)
        }.getOrDefault(false)
    }

    Scaffold(topBar = {
        TopAppBar(title = { Text(L.s(R.string.pr_officer_profile), fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = L.s(R.string.pr_back)) } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = SidebarDark))
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                Card(colors = CardDefaults.cardColors(containerColor = CardDark), border = BorderStroke(1.dp, BorderDark),
                    shape = RoundedCornerShape(16.dp)) {
                    Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                        OfficerAvatar(name = AuthSession.username, size = 64.dp, fontSize = 24.sp)
                        Spacer(Modifier.width(16.dp))
                        Column {
                            Text(AuthSession.username ?: L.s(R.string.pr_officer), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text(roleLabel(AuthSession.role), color = AccentGreen, fontWeight = FontWeight.SemiBold)
                            Text(listOfNotNull(AuthSession.checkpointName, AuthSession.checkpointCode?.let { "($it)" }).joinToString(" ")
                                .ifBlank { L.s(R.string.pr_no_post_assigned) }, color = MutedForeground)
                            AuthSession.loginAt?.let {
                                Text(L.f(R.string.pr_signed_in_at, DateTimeFormatter.ofPattern("dd MMM, HH:mm").withZone(ZoneId.systemDefault()).format(Instant.ofEpochMilli(it))),
                                    color = MutedForeground, style = MaterialTheme.typography.labelSmall)
                            }
                        }
                    }
                }
            }
            item {
                Panel(L.s(R.string.pr_my_work)) {
                    val chipColors = FilterChipDefaults.filterChipColors(selectedContainerColor = AccentGreen, selectedLabelColor = BackgroundDark)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(1 to L.s(R.string.pr_today), 7 to L.s(R.string.pr_7_days), 0 to L.s(R.string.pr_all_time)).forEach { (d, l) ->
                            FilterChip(selected = period == d, onClick = { period = d }, label = { Text(l) }, colors = chipColors)
                        }
                    }
                    Spacer(Modifier.height(10.dp))
                    val risks = inPeriod.mapNotNull { it.riskScore }
                    listOf(
                        Triple(L.s(R.string.pr_documents_checked), "${inPeriod.size}", AccentGreen),
                        Triple(L.s(R.string.pr_passed_all_checks), "${inPeriod.count { it.overallStatus == "PASS" }}", SuccessGreen),
                        Triple(L.s(R.string.pr_cleared_by_me), "${inPeriod.count { it.officerAction == "CLEARED" }}", SuccessGreen),
                        Triple(L.s(R.string.pr_sent_to_admin), "${inPeriod.count { it.officerAction == "SEND_TO_OFFICER" }}", ChartBlue),
                        Triple(L.s(R.string.pr_admin_responses), "${inPeriod.count { it.reviewerResponded == true }}", WarningAmber),
                        Triple(L.s(R.string.pr_awaiting_my_decision), "${inPeriod.count { it.officerAction == "PENDING" }}", WarningAmber),
                        Triple(L.s(R.string.pr_average_risk_indicator), if (risks.isEmpty()) "–" else "${risks.average().toInt()}/100", MutedForeground),
                    ).forEach { (k, v, c) -> Line(k, v, c) }
                }
            }
            item {
                Panel(L.s(R.string.pr_device_and_connection)) {
                    Line(L.s(R.string.pr_phone), "${Build.MANUFACTURER} ${Build.MODEL}")
                    Line(L.s(R.string.pr_android), Build.VERSION.RELEASE)
                    Line(L.s(R.string.pr_app_version), BuildConfig.VERSION_NAME)
                    Line(L.s(R.string.pr_server), BuildConfig.API_BASE_URL.removePrefix("https://").removePrefix("http://").trimEnd('/'))
                    Line(L.s(R.string.pr_connection), ConnectivityMonitor.lastDetail.ifBlank { L.s(R.string.pr_checking) })
                    Line(L.s(R.string.pr_waiting_to_sync), "$pending", if (pending > 0) ChartBlue else MutedForeground)
                }
            }
            item {
                Panel(L.s(R.string.pr_data_on_this_phone)) {
                    Line(L.s(R.string.pr_stored_captures), "$stored")
                    Text(L.f(R.string.pr_data_on_phone_notice, com.pramaanai.officer.data.local.AppSettings.retentionDays(context)),
                        color = MutedForeground,
                        style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(8.dp))
                    if (!confirmClear) OutlinedButton(onClick = { confirmClear = true }, modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp)) {
                        Icon(Icons.Filled.DeleteSweep, null, tint = WarningAmber); Spacer(Modifier.width(8.dp))
                        Text(L.s(R.string.pr_clear_stored_images_from_this), color = WarningAmber)
                    } else Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        OutlinedButton(onClick = { confirmClear = false }, modifier = Modifier.weight(1f)) { Text(L.s(R.string.pr_cancel)) }
                        OutlinedButton(onClick = {
                            scope.launch { CaptureStore.get(context).clearAll(); stored = 0; confirmClear = false }
                        }, modifier = Modifier.weight(1f), border = BorderStroke(1.dp, DestructiveRed)) { Text(L.f(R.string.pr_delete, stored), color = DestructiveRed) }
                    }
                }
            }
            item {
                Panel(L.s(R.string.pr_account)) {
                    Action(Icons.Filled.Settings, L.s(R.string.pr_settings_language_security_display), AccentGreen, onOpenSettings)
                    Action(Icons.AutoMirrored.Filled.HelpOutline, L.s(R.string.pr_replay_the_guided_tour), ChartBlue, onReplayTour)
                    Action(Icons.AutoMirrored.Filled.Logout, L.s(R.string.pr_log_out), DestructiveRed, onLogout)
                }
            }
            item {
                Text(L.s(R.string.pr_registry_lookups_in_this_build),
                    color = MutedForeground, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

private fun roleLabel(role: String?) = when (role) {
    "OFFICER" -> L.s(R.string.pr_field_officer)
    "REVIEWER" -> L.s(R.string.pr_reviewing_officer_admin)
    else -> role ?: L.s(R.string.pr_officer_2)
}

@Composable
private fun Panel(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun Line(label: String, value: String, color: Color = Color.Unspecified) {
    Row(Modifier.fillMaxWidth().padding(vertical = 5.dp)) {
        Text(label, color = MutedForeground, modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.SemiBold, color = color)
    }
}

@Composable
private fun Action(icon: ImageVector, label: String, color: Color, onClick: () -> Unit) {
    OutlinedButton(onClick = onClick, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp).height(52.dp),
        shape = RoundedCornerShape(10.dp), border = BorderStroke(1.dp, BorderDark)) {
        Box(Modifier.size(28.dp).background(color.copy(alpha = 0.15f), CircleShape), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = color, modifier = Modifier.size(16.dp))
        }
        Spacer(Modifier.width(10.dp))
        Text(label, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
    }
}
