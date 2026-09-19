package com.pramaanai.officer.ui.auth

import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.AccentGreen
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.Image
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.pramaanai.officer.R
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.local.LocaleManager
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.filled.Language
import androidx.compose.material3.TextButton
import androidx.compose.ui.platform.LocalContext
import com.pramaanai.officer.data.remote.CheckpointResponse
import com.pramaanai.officer.ui.theme.Gray100
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import com.pramaanai.officer.ui.theme.White
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(repository: ScreeningRepository, onLoggedIn: () -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    var checkpoints by remember { mutableStateOf<List<CheckpointResponse>>(emptyList()) }
    var selectedCheckpoint by remember { mutableStateOf<CheckpointResponse?>(null) }
    var checkpointMenuExpanded by remember { mutableStateOf(false) }
    var languageMenuExpanded by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val currentLanguage = LocaleManager.getSavedLanguageTag(context)
    val scope = rememberCoroutineScope()
    val authFailedMessage = stringResource(R.string.auth_failed_message)

    LaunchedEffect(Unit) {
        try {
            checkpoints = repository.listCheckpoints()
        } catch (_: Exception) {
            // Backend unreachable — the dropdown just stays empty; login
            // itself will fail with a clear error when attempted, so this
            // doesn't need its own error banner.
        }
    }

    fun attemptLogin() {
        errorMessage = null
        loading = true
        scope.launch {
            try {
                repository.login(username.trim(), password, selectedCheckpoint?.code)
                loading = false
                onLoggedIn()
            } catch (e: IllegalStateException) {
                loading = false
                errorMessage = e.message
            } catch (e: Exception) {
                loading = false
                errorMessage = authFailedMessage
            }
        }
    }

    fun getLanguageDisplayName(tag: String): String {
        return when (tag) {
            "system" -> context.getString(R.string.language_system)
            "en" -> context.getString(R.string.language_english)
            "hi" -> context.getString(R.string.language_hindi)
            "ne" -> context.getString(R.string.language_nepali)
            "dz" -> context.getString(R.string.language_dzongkha)
            else -> tag
        }
    }

    Column(modifier = Modifier.fillMaxSize().background(White)) {
        // Language selector at the top
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.End,
            verticalAlignment = Alignment.CenterVertically
        ) {
            ExposedDropdownMenuBox(
                expanded = languageMenuExpanded,
                onExpandedChange = { languageMenuExpanded = it }
            ) {
                TextButton(
                    onClick = { languageMenuExpanded = true },
                    modifier = Modifier.menuAnchor()
                ) {
                    Icon(Icons.Default.Language, contentDescription = null, tint = Ink900)
                    Spacer(Modifier.width(8.dp))
                    Text(getLanguageDisplayName(currentLanguage), color = Ink900)
                }
                DropdownMenu(
                    expanded = languageMenuExpanded,
                    onDismissRequest = { languageMenuExpanded = false }
                ) {
                    LocaleManager.SUPPORTED.forEach { langTag ->
                        DropdownMenuItem(
                            text = { Text(getLanguageDisplayName(langTag)) },
                            onClick = {
                                LocaleManager.setSavedLanguageTag(context, langTag)
                                languageMenuExpanded = false
                                // Restart activity to apply language change
                                (context as? androidx.activity.ComponentActivity)?.recreate()
                            }
                        )
                    }
                }
            }
        }

        // Main login content - using weight to fill remaining space
        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Image(
                painter = painterResource(R.mipmap.ic_launcher_foreground),
                contentDescription = null,
                modifier = Modifier.size(72.dp),
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.login_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold, color = Ink900)
            Text(
                stringResource(R.string.login_subtitle, selectedCheckpoint?.name ?: "Secure Officer Login"),
                style = MaterialTheme.typography.bodyMedium,
                color = Gray600,
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(24.dp))

            // Shown after an involuntary sign-out (expired session, idle
            // timeout) so the officer isn't dropped on a blank login screen
            // with no explanation.
            val notice = remember { com.pramaanai.officer.data.remote.SessionEvents.pendingNotice }
            if (notice != null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(com.pramaanai.officer.ui.theme.WarningAmber.copy(alpha = 0.12f), RoundedCornerShape(8.dp))
                        .padding(12.dp),
                ) {
                    Text(notice, style = MaterialTheme.typography.bodySmall, color = com.pramaanai.officer.ui.theme.WarningAmber)
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(if (notice != null) 16.dp else 12.dp))

            ExposedDropdownMenuBox(
                expanded = checkpointMenuExpanded,
                onExpandedChange = { checkpointMenuExpanded = it },
                modifier = Modifier.fillMaxWidth(),
            ) {
                OutlinedTextField(
                    value = selectedCheckpoint?.let { "${it.name} (${it.code})" } ?: "",
                    onValueChange = {},
                    readOnly = true,
                    label = { Text(stringResource(R.string.common_checkpoint)) },
                    placeholder = { Text(if (checkpoints.isEmpty()) stringResource(R.string.common_loading_checkpoints) else stringResource(R.string.common_select_checkpoint)) },
                    trailingIcon = {
                        ExposedDropdownMenuDefaults.TrailingIcon(expanded = checkpointMenuExpanded)
                    },
                    modifier = Modifier.fillMaxWidth().menuAnchor(),
                    colors = fieldColors(),
                )
                DropdownMenu(
                    expanded = checkpointMenuExpanded,
                    onDismissRequest = { checkpointMenuExpanded = false },
                ) {
                    checkpoints.forEach { cp ->
                        DropdownMenuItem(
                            text = { Text("${cp.name} (${cp.code})") },
                            onClick = {
                                selectedCheckpoint = cp
                                checkpointMenuExpanded = false
                            },
                        )
                    }
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(14.dp))

            OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                label = { Text(stringResource(R.string.login_officer_id)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                colors = fieldColors(),
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(14.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text(stringResource(R.string.login_password)) },
                singleLine = true,
                visualTransformation = if (showPassword) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showPassword = !showPassword }) {
                        Icon(
                            if (showPassword) Icons.Filled.VisibilityOff else Icons.Filled.Visibility,
                            contentDescription = if (showPassword) stringResource(R.string.common_hide_password) else stringResource(R.string.common_show_password),
                        )
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                colors = fieldColors(),
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))

            if (errorMessage != null) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(Gray100, RoundedCornerShape(8.dp))
                        .padding(12.dp),
                ) {
                    Text(errorMessage.orEmpty(), style = MaterialTheme.typography.bodySmall, color = Ink900)
                }
                androidx.compose.foundation.layout.Spacer(Modifier.height(8.dp))
            }

            androidx.compose.foundation.layout.Spacer(Modifier.height(12.dp))
            Button(
                onClick = { attemptLogin() },
                enabled = username.isNotBlank() && password.isNotBlank() && !loading,
                colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(10.dp),
            ) {
                if (loading) {
                    CircularProgressIndicator(modifier = Modifier.size(20.dp), color = White, strokeWidth = 2.dp)
                } else {
                    Text(stringResource(R.string.common_sign_in), fontWeight = FontWeight.SemiBold)
                }
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(20.dp))
            Text(
                stringResource(R.string.login_footer),
                style = MaterialTheme.typography.labelSmall,
                color = Gray500,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
            )
        }
    }
}

@Composable
private fun fieldColors() = OutlinedTextFieldDefaults.colors(
    focusedBorderColor = Ink900,
    unfocusedBorderColor = Gray200,
    focusedLabelColor = Ink900,
)
