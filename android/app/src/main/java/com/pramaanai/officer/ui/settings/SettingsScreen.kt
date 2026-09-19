package com.pramaanai.officer.ui.settings

import com.pramaanai.officer.ui.theme.AccentGreen
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
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.local.LocaleManager
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900

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
                        Triple("system", stringResource(R.string.language_system), false),
                        Triple("en", stringResource(R.string.language_english), false),
                        Triple("hi", stringResource(R.string.language_hindi), false),
                        Triple("ne", stringResource(R.string.language_nepali), false),
                        Triple("bn", stringResource(R.string.language_bengali), false),
                        Triple("pa", stringResource(R.string.language_punjabi), false),
                        Triple("as", stringResource(R.string.language_assamese), false),
                        Triple("dz", stringResource(R.string.language_dzongkha), false),
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
                SettingsSection(stringResource(R.string.settings_account)) {
                    SettingsInfoRow(stringResource(R.string.settings_officer_id), profile.officerId)
                    SettingsInfoRow(stringResource(R.string.settings_role), profile.role)
                    SettingsInfoRow(stringResource(R.string.settings_checkpoint_label), profile.checkpoint)
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection(stringResource(R.string.settings_notifications)) {
                    SettingsToggleRow(stringResource(R.string.settings_push_notifications), pushNotifications) { pushNotifications = it }
                    SettingsToggleRow(stringResource(R.string.settings_high_risk_only), highRiskAlertsOnly) { highRiskAlertsOnly = it }
                    Text(
                        stringResource(R.string.settings_local_only_notice),
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection(stringResource(R.string.settings_risk_config)) {
                    Text(
                        stringResource(R.string.settings_risk_signals_desc),
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(6.dp))
                    Text(
                        stringResource(R.string.settings_risk_weights_desc),
                        style = MaterialTheme.typography.labelSmall,
                        color = Gray600,
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection(stringResource(R.string.settings_document)) {
                    SettingsInfoRow(stringResource(R.string.settings_accepted_types), stringResource(R.string.settings_accepted_types_value))
                    SettingsInfoRow(stringResource(R.string.settings_cross_validation), stringResource(R.string.settings_enabled))
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                SettingsSection(stringResource(R.string.settings_system_prefs)) {
                    SettingsInfoRow(stringResource(R.string.settings_theme), stringResource(R.string.settings_theme_value))
                    SettingsInfoRow(stringResource(R.string.settings_backend), "http://127.0.0.1:8000 (via adb reverse)")
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
            colors = SwitchDefaults.colors(checkedTrackColor = AccentGreen, checkedThumbColor = androidx.compose.ui.graphics.Color.White),
        )
    }
}
