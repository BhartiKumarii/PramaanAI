package com.pramaanai.officer.ui.shell

import com.pramaanai.officer.ui.theme.AccentGreen
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.DocumentScanner
import androidx.compose.material.icons.automirrored.filled.HelpOutline
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.automirrored.filled.ViewList
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Badge
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.R
import com.pramaanai.officer.data.connectivity.ConnectivityState
import com.pramaanai.officer.ui.components.GridPatternBackground
import com.pramaanai.officer.ui.components.OfficerAvatar
import com.pramaanai.officer.ui.components.SystemStatusIndicator
import com.pramaanai.officer.ui.tour.tourAnchor
import com.pramaanai.officer.ui.theme.Gray500
import com.pramaanai.officer.ui.theme.SidebarDark
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class ShellTab(val labelRes: Int, val icon: ImageVector) {
    DASHBOARD(R.string.nav_dashboard, Icons.Filled.Dashboard),
    VERIFY(R.string.nav_verify, Icons.Filled.DocumentScanner),
    QUEUE(R.string.nav_queue, Icons.AutoMirrored.Filled.ViewList),
    HISTORY(R.string.nav_history, Icons.Filled.History),
    MORE(R.string.nav_more, Icons.Filled.MoreHoriz),
}

@Composable
fun ShellTab.label(): String = stringResource(labelRes)

/** Global shell: top bar (title, search, alerts, officer profile, system
 * status + date/time) and bottom navigation across the five top-level
 * sections — the mobile equivalent of the spec's sidebar + top bar
 * structure. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppShell(
    title: String,
    selectedTab: ShellTab,
    onTabSelected: (ShellTab) -> Unit,
    onSearchClick: (() -> Unit)? = null,
    onProfileClick: () -> Unit,
    onAlertsClick: (() -> Unit)? = null,
    onHelpClick: () -> Unit = {},
    officerName: String? = null,
    alertCount: Int = 0,
    connectivityState: ConnectivityState = ConnectivityState.OFFLINE,
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text(title, fontWeight = FontWeight.Bold) },
                    actions = {
                        if (onSearchClick != null) {
                            IconButton(onClick = onSearchClick) {
                                Icon(Icons.Filled.Search, contentDescription = "Search")
                            }
                        }
                        IconButton(onClick = onHelpClick) {
                            Icon(Icons.AutoMirrored.Filled.HelpOutline, contentDescription = "Replay guided tour")
                        }
                        IconButton(onClick = { onAlertsClick?.invoke() ?: onTabSelected(ShellTab.QUEUE) },
                            modifier = Modifier.tourAnchor("notifications_bell")) {
                            BadgedBox(badge = { if (alertCount > 0) Badge { Text("$alertCount") } }) {
                                Icon(Icons.Filled.Notifications, contentDescription = "Alerts")
                            }
                        }
                        IconButton(onClick = onProfileClick) {
                            OfficerAvatar(name = officerName, size = 28.dp, fontSize = 12.sp)
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = SidebarDark),
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .tourAnchor("status_bar")
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    SystemStatusIndicator(state = connectivityState)
                    Text(currentDateTime(), style = MaterialTheme.typography.labelMedium, color = Gray500)
                }
            }
        },
        bottomBar = {
            NavigationBar(containerColor = SidebarDark, tonalElevation = 0.dp, modifier = Modifier.tourAnchor("bottom_nav")) {
                ShellTab.entries.forEach { tab ->
                    val label = tab.label()
                    NavigationBarItem(
                        selected = tab == selectedTab,
                        onClick = { onTabSelected(tab) },
                        icon = { Icon(tab.icon, contentDescription = label) },
                        label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                        colors = androidx.compose.material3.NavigationBarItemDefaults.colors(
                            selectedIconColor = AccentGreen,
                            selectedTextColor = AccentGreen,
                            indicatorColor = AccentGreen.copy(alpha = 0.18f),
                            unselectedIconColor = Gray500,
                            unselectedTextColor = Gray500,
                        ),
                    )
                }
            }
        },
    ) { padding ->
        // Applied once here so every bottom-nav tab shares the same green
        // grid backdrop as the web console/landing page, instead of each
        // screen opting in individually and drifting out of sync.
        GridPatternBackground(modifier = Modifier.padding(padding), animated = true) {
            content(PaddingValues(0.dp))
        }
    }
}

private fun currentDateTime(): String =
    SimpleDateFormat("dd MMM, HH:mm", Locale.getDefault()).format(Date())
