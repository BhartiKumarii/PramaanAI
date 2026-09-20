package com.pramaanai.officer.ui.profile

import com.pramaanai.officer.ui.theme.BackgroundDark
import com.pramaanai.officer.ui.theme.AccentGreen
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.Permissions
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.ui.components.OfficerAvatar
import com.pramaanai.officer.ui.theme.Gray200
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.Gray600
import com.pramaanai.officer.ui.theme.Ink900
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfficerProfileScreen(repository: ScreeningRepository, onBack: () -> Unit, onLogout: () -> Unit, onOpenSettings: () -> Unit) {
    val profile = repository.officerProfile()
    val recentActivity by repository.observeAuditLog().collectAsStateWithLifecycle(initialValue = emptyList())
    val myActivity = recentActivity.filter { it.officer == profile.officerId }.take(6)
    val failedLoginAttempts = recentActivity.count { it.officer == profile.officerId && it.result.startsWith("FAILED") }

    Scaffold(topBar = { TopAppBar(title = { Text(stringResource(R.string.title_officer_profile)) }) }) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp)) {
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OfficerAvatar(name = profile.officerId, size = 56.dp, fontSize = 20.sp)
                    Spacer(Modifier.width(14.dp))
                    Column {
                        Text(profile.officerId, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                        Text(Permissions.roleLabel(profile.role), style = MaterialTheme.typography.bodySmall, color = Gray600)
                    }
                }
                Spacer(Modifier.height(20.dp))
            }
            item {
                ProfileSection("Personal Information") {
                    InfoRow("Officer ID", profile.officerId)
                    InfoRow("Role", profile.role)
                    InfoRow("Checkpoint", profile.checkpoint)
                    InfoRow("Account status", "Active")
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                ProfileSection("Security") {
                    InfoRow("Secure session", "Active")
                    InfoRow(
                        "Last login",
                        profile.lastLoginAt?.let { SimpleDateFormat("dd MMM yyyy, HH:mm", Locale.getDefault()).format(Date(it)) } ?: "—",
                    )
                    InfoRow("Session token", "Held in memory for this app session only")
                    InfoRow("Idle timeout", "Warns after 5 min inactivity, signs out 30s later")
                    InfoRow("Failed login attempts", "$failedLoginAttempts recorded")
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                ProfileSection("Account Settings") {
                    Text(
                        "Language, notifications, and system preferences",
                        style = MaterialTheme.typography.bodySmall,
                        color = Gray600,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable(onClick = onOpenSettings)
                            .padding(vertical = 2.dp),
                    )
                }
                Spacer(Modifier.height(12.dp))
            }
            item {
                ProfileSection("Activity") {
                    if (myActivity.isEmpty()) {
                        Text(stringResource(R.string.no_activity_recorded), style = MaterialTheme.typography.bodySmall, color = Gray500)
                    } else {
                        myActivity.forEach { entry ->
                            Text(
                                "${entry.action} — ${SimpleDateFormat("dd MMM, HH:mm", Locale.getDefault()).format(Date(entry.timestamp))}",
                                style = MaterialTheme.typography.bodySmall,
                                modifier = Modifier.padding(vertical = 3.dp),
                            )
                        }
                    }
                }
                Spacer(Modifier.height(20.dp))
            }
            item {
                Button(
                    onClick = onLogout,
                    colors = ButtonDefaults.buttonColors(containerColor = AccentGreen, contentColor = BackgroundDark),
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                ) { Text(stringResource(R.string.button_log_out)) }
            }
        }
    }
}

@Composable
private fun ProfileSection(title: String, content: @Composable androidx.compose.foundation.layout.ColumnScope.() -> Unit) {
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
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 3.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = Gray600)
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Medium)
    }
}
