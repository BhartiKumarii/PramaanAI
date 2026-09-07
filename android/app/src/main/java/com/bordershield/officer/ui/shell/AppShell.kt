package com.bordershield.officer.ui.shell

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.MoreHoriz
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.ViewList
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
import com.bordershield.officer.R
import com.bordershield.officer.ui.components.SystemStatusIndicator
import com.bordershield.officer.ui.tour.tourAnchor
import com.bordershield.officer.ui.theme.Gray500
import com.bordershield.officer.ui.theme.Ink900
import com.bordershield.officer.ui.theme.White
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class ShellTab(val labelRes: Int, val icon: ImageVector) {
    DASHBOARD(R.string.nav_dashboard, Icons.Filled.Dashboard),
    QUEUE(R.string.nav_queue, Icons.Filled.ViewList),
    HISTORY(R.string.nav_history, Icons.Filled.History),
    ALERTS(R.string.nav_alerts, Icons.Filled.Notifications),
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
    onHelpClick: () -> Unit = {},
    alertCount: Int = 0,
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
                            Icon(Icons.Filled.HelpOutline, contentDescription = "Replay guided tour")
                        }
                        IconButton(onClick = { onTabSelected(ShellTab.ALERTS) }) {
                            BadgedBox(badge = { if (alertCount > 0) Badge { Text("$alertCount") } }) {
                                Icon(Icons.Filled.Notifications, contentDescription = "Alerts")
                            }
                        }
                        IconButton(onClick = onProfileClick) {
                            Box(
                                modifier = Modifier.size(28.dp).background(Ink900, CircleShape),
                                contentAlignment = Alignment.Center,
                            ) {
                                Icon(Icons.Filled.Person, contentDescription = "Officer profile", tint = White, modifier = Modifier.size(16.dp))
                            }
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = White),
                )
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    SystemStatusIndicator()
                    Text(currentDateTime(), style = MaterialTheme.typography.labelMedium, color = Gray500)
                }
            }
        },
        bottomBar = {
            NavigationBar(containerColor = White, tonalElevation = 0.dp, modifier = Modifier.tourAnchor("bottom_nav")) {
                ShellTab.entries.forEach { tab ->
                    val label = tab.label()
                    NavigationBarItem(
                        selected = tab == selectedTab,
                        onClick = { onTabSelected(tab) },
                        icon = { Icon(tab.icon, contentDescription = label) },
                        label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                        colors = androidx.compose.material3.NavigationBarItemDefaults.colors(
                            selectedIconColor = White,
                            selectedTextColor = Ink900,
                            indicatorColor = Ink900,
                            unselectedIconColor = Gray500,
                            unselectedTextColor = Gray500,
                        ),
                    )
                }
            }
        },
    ) { padding -> content(padding) }
}

private fun currentDateTime(): String =
    SimpleDateFormat("dd MMM, HH:mm", Locale.getDefault()).format(Date())
