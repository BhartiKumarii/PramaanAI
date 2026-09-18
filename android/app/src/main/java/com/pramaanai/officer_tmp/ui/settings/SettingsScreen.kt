package com.bordershield.officer.ui.settings

import android.app.Activity
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
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.R
import com.bordershield.officer.data.CHECKPOINT
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.local.LocaleManager
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(repository: ScreeningRepository, onBack: () -> Unit) {
    val profile = repository.officerProfile()
    var pushNotifications by remember { mutableStateOf(true) }
    var highRiskAlertsOnly by remember { mutableStateOf(false) }
    val context = LocalContext.current
    var selectedLanguage by remember { mutableStateOf(LocaleManager.getSavedLanguageTag(context)) }

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.settings_title)) }) }) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            item {
                SettingsSection(stringResource(R.string.settings_language_section)) {
                    Text(
                        stringResource(R.string.settings_language_label),
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray600,
                    )
                    Spacer(Modifier.height(10.dp))
                    val unverifiedCaption = stringResource(R.string.language_unverified_notice)
                    val languageOptions = listOf(
                        Triple("en", stringResource(R.string.language_english), false),
                        Triple("hi", stringResource(R.string.language_hindi), false),
                        Triple("ne", stringResource(R.string.language_nepali), false),
                        Triple("bn", stringResource(R.string.language_bengali), false),
                        Triple("pa", stringResource(R.string.language_punjabi), false),
                        Triple("as", stringResource(R.string.language_assamese), false),
                        Triple("dz", stringResource(R.string.language_dzongkha), true),
                    )
                    languageOptions.forEach { (tag, label, unverified) ->
                        LanguageOptionRow(
                            tag = tag,
                            label = label,
                            selected = selectedLanguage == tag,
                            onSelect = { selectedLanguage = tag; applyLanguage(context, tag) },
                            caption = if (unverified) unverifiedCaption else null,
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection("Account Settings") {
                    SettingsInfoRow("Officer ID", profile.officerId)
                    SettingsInfoRow("Role", profile.role)
                    SettingsInfoRow("Checkpoint", CHECKPOINT)
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection("Notification Settings") {
                    SettingsToggleRow("Push notifications for new alerts", pushNotifications) { pushNotifications = it }
                    SettingsToggleRow("Only notify for high-risk cases", highRiskAlertsOnly) { highRiskAlertsOnly = it }
                    Text(
                        "Stored on this device only — not synced to the backend in this build.",
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection("Screening Rules & Risk Configuration") {
                    Text(
                        "Signals combined into the risk score: document checksum/MRZ validation, " +
                            "forensics (ELA), deepfake heuristic, blacklist/registry lookup, face match, " +
                            "identity graph, and liveness heuristic.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Weights and thresholds are configured and enforced server-side by the scoring " +
                            "engine only — this app cannot read or set them, and no UI path here can ever " +
                            "submit a manually chosen score.",
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection("Document Settings") {
                    SettingsInfoRow("Accepted document types", "Passport, National ID, Visa")
                    SettingsInfoRow("Front/back cross-validation", "Enabled")
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection("System Preferences") {
                    SettingsInfoRow("Theme", "Follows system light/dark setting")
                    SettingsInfoRow("Backend", "http://127.0.0.1:8000 (via adb reverse)")
                }
            }
        }
    }
}

private fun applyLanguage(context: android.content.Context, tag: String) {
    LocaleManager.setSavedLanguageTag(context, tag)
    (context as? Activity)?.recreate()
}

@Composable
private fun LanguageOptionRow(
    tag: String,
    label: String,
    selected: Boolean,
    onSelect: () -> Unit,
    caption: String? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(label, style = MaterialTheme.typography.bodyMedium)
            if (caption != null) {
                Text("(${caption})", style = MaterialTheme.typography.labelSmall, color = Gray600)
            }
        }
        FilterChip(selected = selected, onClick = onSelect, label = { Text(if (selected) "Selected" else "Select") })
    }
}

@Composable
private fun SettingsSection(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        border = BorderStroke(1.dp, Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

@Composable
private fun SettingsInfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Gray600)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}

@Composable
private fun SettingsToggleRow(label: String, checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(label, style = MaterialTheme.typography.bodySmall, modifier = Modifier.weight(1f))
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            colors = SwitchDefaults.colors(checkedTrackColor = Ink900, checkedThumbColor = androidx.compose.ui.graphics.Color.White),
        )
    }
}
