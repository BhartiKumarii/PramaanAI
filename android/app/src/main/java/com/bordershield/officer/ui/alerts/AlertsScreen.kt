package com.bordershield.officer.ui.alerts

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.model.AlertCategory
import com.bordershield.officer.data.model.AlertItem
import com.bordershield.officer.ui.components.EmptyState
import com.bordershield.officer.ui.theme.Gray100
import com.bordershield.officer.ui.theme.Gray200
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Ink900
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun AlertsScreen(repository: ScreeningRepository, padding: PaddingValues, onOpenScreening: (String) -> Unit) {
    val alerts by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())

    if (alerts.isEmpty()) {
        Column(modifier = Modifier.fillMaxSize().padding(padding)) {
            EmptyState("No active alerts", "Cases requiring officer attention will appear here.")
        }
        return
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 12.dp),
    ) {
        items(alerts, key = { it.id }) { alert ->
            AlertRow(alert, onClick = { onOpenScreening(alert.screeningId) })
            Spacer(Modifier.height(8.dp))
        }
    }
}

private fun categoryLabel(category: AlertCategory): String = when (category) {
    AlertCategory.DOCUMENT_REVIEW_REQUIRED -> "Document Review Required"
    AlertCategory.RISK_ASSESSMENT_REVIEW -> "Risk Assessment Requires Review"
    AlertCategory.DUPLICATE_RECORD -> "Duplicate Record"
    AlertCategory.INCOMPLETE_INFORMATION -> "Incomplete Information"
    AlertCategory.VERIFICATION_REQUIRED -> "Verification Required"
}

@Composable
private fun AlertRow(alert: AlertItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable(onClick = onClick),
        border = BorderStroke(1.dp, Gray200),
        shape = RoundedCornerShape(10.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                androidx.compose.material3.Text(
                    categoryLabel(alert.category).uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = Ink900,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier
                        .background(Gray100, RoundedCornerShape(6.dp))
                        .padding(horizontal = 8.dp, vertical = 3.dp),
                )
                Text(timeAgo(alert.createdAt), style = MaterialTheme.typography.labelSmall, color = Gray500)
            }
            Spacer(Modifier.height(6.dp))
            Text(alert.travelerName, fontWeight = FontWeight.SemiBold)
            Text(alert.description, style = MaterialTheme.typography.bodySmall, color = Gray500)
        }
    }
}

private fun timeAgo(timestamp: Long): String {
    val diffMs = System.currentTimeMillis() - timestamp
    val minutes = diffMs / (60 * 1000)
    return when {
        minutes < 1 -> "just now"
        minutes < 60 -> "${minutes}m ago"
        minutes < 60 * 24 -> "${minutes / 60}h ago"
        else -> SimpleDateFormat("dd MMM", Locale.getDefault()).format(Date(timestamp))
    }
}
