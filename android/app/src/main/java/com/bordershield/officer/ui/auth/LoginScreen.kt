package com.bordershield.officer.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.bordershield.officer.R
import com.bordershield.officer.data.CHECKPOINT
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.ui.theme.Gray100
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Gray600
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White
import kotlinx.coroutines.launch

@Composable
fun LoginScreen(repository: ScreeningRepository, onLoggedIn: () -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var showPassword by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun attemptLogin() {
        errorMessage = null
        loading = true
        scope.launch {
            try {
                repository.login(username.trim(), password)
                loading = false
                onLoggedIn()
            } catch (e: Exception) {
                loading = false
                errorMessage = "Authentication failed — check officer ID and password, and that the backend is reachable."
            }
        }
    }

    Box(modifier = Modifier.fillMaxSize().background(White)) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 28.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Box(
                modifier = Modifier.size(64.dp).background(Ink900, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Icon(Icons.Filled.Shield, contentDescription = null, tint = White, modifier = Modifier.size(32.dp))
            }
            androidx.compose.foundation.layout.Spacer(Modifier.height(20.dp))
            Text(stringResource(R.string.login_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(
                stringResource(R.string.login_subtitle, CHECKPOINT),
                style = MaterialTheme.typography.bodyMedium,
                color = Gray600,
            )
            androidx.compose.foundation.layout.Spacer(Modifier.height(36.dp))

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
                            contentDescription = if (showPassword) "Hide password" else "Show password",
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
                colors = ButtonDefaults.buttonColors(containerColor = Ink900, contentColor = White),
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
