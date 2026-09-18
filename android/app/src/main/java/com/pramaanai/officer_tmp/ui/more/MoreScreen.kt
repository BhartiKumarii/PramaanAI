package com.bordershield.officer.ui.more

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Logout
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Ink900

@Composable
fun MoreScreen(
    padding: PaddingValues,
    role: String?,
    onOpenAnalytics: () -> Unit,
    onOpenAuditLog: () -> Unit,
    onOpenOfficerProfile: () -> Unit,
    onOpenSettings: () -> Unit,
    onLogout: () -> Unit,
) {
    Column(modifier = Modifier.fillMaxSize().padding(padding).padding(12.dp)) {
        MoreRow("Analytics", Icons.Filled.Analytics, onOpenAnalytics)
        Spacer(Modifier.height(8.dp))
        // Audit Log is read-only for every role (per-officer view of real
        // events) and Settings holds personal preferences (language,
        // notifications) alongside admin-only sections — so both stay
        // visible to every role; only specific sensitive controls inside
        // Settings are gated (see SettingsScreen.kt), not the screen itself.
        MoreRow("Audit Log", Icons.Filled.History, onOpenAuditLog)
        Spacer(Modifier.height(8.dp))
        MoreRow("Officer Profile", Icons.Filled.Person, onOpenOfficerProfile)
        Spacer(Modifier.height(8.dp))
        MoreRow("Settings", Icons.Filled.Settings, onOpenSettings)
        Spacer(Modifier.height(8.dp))
        MoreRow("Logout", Icons.Filled.Logout, onLogout)
    }
}

@Composable
private fun MoreRow(label: String, icon: ImageVector, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        border = BorderStroke(1.dp, Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null, tint = Ink900)
                Spacer(Modifier.width(12.dp))
                Text(label, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
            }
            Icon(Icons.Filled.ChevronRight, contentDescription = null, tint = Gray500, modifier = Modifier.height(20.dp))
        }
    }
}
