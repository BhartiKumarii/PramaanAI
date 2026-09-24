package com.pramaanai.officer.ui.settings

import com.pramaanai.officer.ui.i18n.L
import android.app.Activity
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.DocumentScanner
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.BuildConfig
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.connectivity.ConnectivityMonitor
import com.pramaanai.officer.data.docverify.CaptureStore
import com.pramaanai.officer.data.docverify.OnDeviceRegionDetector
import com.pramaanai.officer.data.local.AppSettings
import com.pramaanai.officer.data.local.LocaleManager
import com.pramaanai.officer.data.remote.RetrofitClient
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.BorderDark
import com.pramaanai.officer.ui.theme.CardDark
import com.pramaanai.officer.ui.theme.MutedForeground
import com.pramaanai.officer.ui.theme.SidebarDark
import com.pramaanai.officer.ui.theme.WarningAmber
import kotlinx.coroutines.launch

/** Settings that take effect — each is read by the code it controls
 * (AppSettings usages). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(@Suppress("UNUSED_PARAMETER") repository: ScreeningRepository, onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var language by remember { mutableStateOf(LocaleManager.getSavedLanguageTag(context)) }
    var route by remember { mutableStateOf(AppSettings.defaultRoute(context)) }
    var askLive by remember { mutableStateOf(AppSettings.askLivePhoto(context)) }
    var retention by remember { mutableIntStateOf(AppSettings.retentionDays(context)) }
    var poll by remember { mutableIntStateOf(AppSettings.responsePollSeconds(context)) }
    var levels by remember { mutableStateOf(AppSettings.alertLevels(context)) }
    var lock by remember { mutableIntStateOf(AppSettings.autoLockMinutes(context)) }
    var testResult by remember { mutableStateOf<String?>(null) }
    var stored by remember { mutableIntStateOf(-1) }
    androidx.compose.runtime.LaunchedEffect(Unit) { stored = CaptureStore.get(context).count() }

    Scaffold(topBar = {
        TopAppBar(title = { Text(stringResource(R.string.settings_title), fontWeight = FontWeight.Bold) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = L.s(R.string.st_back)) } },
            colors = TopAppBarDefaults.topAppBarColors(containerColor = SidebarDark))
    }) { padding ->
        LazyColumn(Modifier.fillMaxSize().padding(padding), contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)) {
            item {
                Section(Icons.Filled.Language, stringResource(R.string.settings_language_section)) {
                    val options = listOf("system" to stringResource(R.string.language_system), "en" to stringResource(R.string.language_english),
                        "hi" to stringResource(R.string.language_hindi), "ne" to stringResource(R.string.language_nepali),
                        "bn" to stringResource(R.string.language_bengali), "pa" to stringResource(R.string.language_punjabi),
                        "as" to stringResource(R.string.language_assamese), "dz" to stringResource(R.string.language_dzongkha))
                    Choice(stringResource(R.string.settings_language_label), language, options) { tag ->
                        language = tag
                        LocaleManager.setSavedLanguageTag(context, tag)
                        (context as? Activity)?.recreate()
                    }
                    Hint(L.s(R.string.st_screens_change_language_immediately_document))
                }
            }
            item {
                Section(Icons.Filled.DocumentScanner, L.s(R.string.st_verification)) {
                    Choice(L.s(R.string.st_default_crossing), route ?: "POST", listOf("POST" to L.s(R.string.st_from_my_post), "INDIA_NEPAL" to L.s(R.string.st_india_nepal),
                        "INDIA_BHUTAN" to L.s(R.string.st_india_bhutan))) { v ->
                        route = if (v == "POST") null else v
                        AppSettings.setDefaultRoute(context, route)
                    }
                    Toggle(L.s(R.string.st_ask_for_a_live_photo), askLive) { askLive = it; AppSettings.setAskLivePhoto(context, it) }
                    Hint(L.s(R.string.st_when_off_verification_goes_straight))
                    Choice(L.s(R.string.st_keep_captures_on_this_phone), retention, listOf(7 to L.s(R.string.st_7_days), 30 to L.s(R.string.st_30_days), 90 to L.s(R.string.st_90_days))) {
                        retention = it; AppSettings.setRetentionDays(context, it)
                    }
                    Hint(if (stored >= 0) L.f(R.string.st_capture_s_stored_now_encrypted, stored) else "")
                }
            }
            item {
                Section(Icons.Filled.Notifications, L.s(R.string.st_notifications)) {
                    Choice(L.s(R.string.st_check_for_admin_responses), poll, listOf(15 to L.s(R.string.st_every_15_seconds), 30 to L.s(R.string.st_every_30_seconds),
                        120 to L.s(R.string.st_every_2_minutes), 0 to L.s(R.string.st_only_when_i_open_a))) { poll = it; AppSettings.setResponsePollSeconds(context, it) }
                    Text(L.s(R.string.st_risk_alerts_to_show), color = MutedForeground, style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.padding(top = 8.dp))
                    listOf("HIGH" to L.s(R.string.st_high_risk), "MEDIUM" to L.s(R.string.st_medium_risk), "LOW" to L.s(R.string.st_low_risk)).forEach { (lvl, label) ->
                        Toggle(label, lvl in levels) { on ->
                            levels = if (on) levels + lvl else levels - lvl
                            AppSettings.setAlertLevels(context, levels)
                        }
                    }
                }
            }
            item {
                Section(Icons.Filled.Lock, L.s(R.string.st_security)) {
                    Choice(L.s(R.string.st_lock_after_inactivity), lock, listOf(5 to L.s(R.string.st_5_minutes), 10 to L.s(R.string.st_10_minutes), 15 to L.s(R.string.st_15_minutes),
                        30 to L.s(R.string.st_30_minutes))) { lock = it; AppSettings.setAutoLockMinutes(context, it) }
                    Hint(L.s(R.string.st_you_are_warned_first_then))
                    OutlinedButton(onClick = { scope.launch { CaptureStore.get(context).clearAll(); stored = 0 } },
                        modifier = Modifier.fillMaxWidth().padding(top = 6.dp), shape = RoundedCornerShape(10.dp),
                        border = BorderStroke(1.dp, WarningAmber)) {
                        Text(L.s(R.string.st_clear_stored_document_images_and), color = WarningAmber)
                    }
                }
            }
            item {
                Section(Icons.Filled.Wifi, L.s(R.string.st_connection)) {
                    Row(Modifier.fillMaxWidth()) {
                        Text(L.s(R.string.st_server), color = MutedForeground, modifier = Modifier.weight(1f))
                        Text(BuildConfig.API_BASE_URL.removePrefix("https://").removePrefix("http://").trimEnd('/'),
                            fontWeight = FontWeight.SemiBold)
                    }
                    OutlinedButton(onClick = {
                        testResult = L.s(R.string.st_testing)
                        scope.launch {
                            val state = ConnectivityMonitor(context, RetrofitClient.apiService).check()
                            testResult = "${state.name.lowercase().replaceFirstChar { it.uppercase() }} — ${ConnectivityMonitor.lastDetail}"
                        }
                    }, modifier = Modifier.fillMaxWidth().padding(top = 8.dp), shape = RoundedCornerShape(10.dp)) {
                        Text(L.s(R.string.st_test_connection), color = AccentGreen)
                    }
                    testResult?.let { Hint(it) }
                }
            }
            item {
                Section(Icons.Filled.Info, L.s(R.string.st_about)) {
                    Info(L.s(R.string.st_app_version), BuildConfig.VERSION_NAME)
                    Info(L.s(R.string.st_region_detector_on_phone), OnDeviceRegionDetector.NAME)
                    Info(L.s(R.string.st_text_reading_on_phone), L.s(R.string.st_ml_kit_text_recognition))
                    Info(L.s(R.string.st_server_checks), L.s(R.string.st_pp_ocr_mrz_icao_9303))
                    Hint(L.s(R.string.st_registry_lookups_in_this_build) + " " +
                        L.s(R.string.st_the_system_assists_the_officer))
                }
            }
        }
    }
}

@Composable
private fun Section(icon: ImageVector, title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = CardDark),
        border = BorderStroke(1.dp, BorderDark), shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = AccentGreen, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
            Spacer(Modifier.height(6.dp))
            content()
        }
    }
}

@Composable
private fun Hint(text: String) {
    if (text.isNotBlank()) Text(text, color = MutedForeground, style = MaterialTheme.typography.bodySmall)
}

@Composable
private fun Info(label: String, value: String) {
    Row(Modifier.fillMaxWidth().padding(vertical = 3.dp)) {
        Text(label, color = MutedForeground, modifier = Modifier.weight(1f))
        Text(value, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1.2f))
    }
}

@Composable
private fun Toggle(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Switch(checked = checked, onCheckedChange = onChange,
            colors = SwitchDefaults.colors(checkedThumbColor = BackgroundDark, checkedTrackColor = AccentGreen))
    }
}

@Composable
private fun <T> Choice(label: String, selected: T, options: List<Pair<T, String>>, onPick: (T) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(label, modifier = Modifier.weight(1f))
        Box {
            OutlinedButton(onClick = { open = true }, shape = RoundedCornerShape(10.dp)) {
                Text(options.firstOrNull { it.first == selected }?.second ?: "—", color = AccentGreen)
                Icon(Icons.Filled.ArrowDropDown, null, tint = MutedForeground)
            }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                options.forEach { (v, l) ->
                    DropdownMenuItem(text = { Text(l, fontWeight = if (v == selected) FontWeight.Bold else FontWeight.Normal) },
                        onClick = { open = false; onPick(v) })
                }
            }
        }
    }
}
