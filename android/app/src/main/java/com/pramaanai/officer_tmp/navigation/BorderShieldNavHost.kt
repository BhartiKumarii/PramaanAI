package com.bordershield.officer.navigation

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bordershield.officer.R
import com.bordershield.officer.data.local.TourPreferences
import com.bordershield.officer.ui.session.SessionTimeoutMonitor
import com.bordershield.officer.ui.tour.PracticeWorkflowScreen
import com.bordershield.officer.ui.tour.TourOverlay
import com.bordershield.officer.ui.tour.TourState
import com.bordershield.officer.ui.tour.TourStep
import kotlinx.coroutines.launch
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.remote.AuthSession
import com.bordershield.officer.ui.alerts.AlertsScreen
import com.bordershield.officer.ui.analytics.AnalyticsScreen
import com.bordershield.officer.ui.audit.AuditLogScreen
import com.bordershield.officer.ui.auth.LoginScreen
import com.bordershield.officer.ui.capture.CaptureScreen
import com.bordershield.officer.ui.dashboard.DashboardScreen
import com.bordershield.officer.ui.history.HistoryScreen
import com.bordershield.officer.ui.more.MoreScreen
import com.bordershield.officer.ui.newscreening.NewScreeningScreen
import com.bordershield.officer.ui.profile.OfficerProfileScreen
import com.bordershield.officer.ui.queue.QueueScreen
import com.bordershield.officer.ui.review.ReviewScreen
import com.bordershield.officer.ui.settings.SettingsScreen
import com.bordershield.officer.ui.shell.AppShell
import com.bordershield.officer.ui.shell.ShellTab
import com.bordershield.officer.ui.traveler.TravelerProfileScreen
import com.bordershield.officer.ui.workflow.WorkflowResultScreen

object Routes {
    const val LOGIN = "login"
    const val DASHBOARD = "dashboard"
    const val QUEUE = "queue"
    const val HISTORY = "history"
    const val ALERTS = "alerts"
    const val MORE = "more"
    const val ANALYTICS = "analytics"
    const val AUDIT_LOG = "audit_log"
    const val OFFICER_PROFILE = "officer_profile"
    const val SETTINGS = "settings"
    const val NEW_SCREENING = "new_screening"
    const val CAPTURE = "capture/{travelerName}/{documentType}/{nationality}"
    const val WORKFLOW = "workflow/{screeningId}"
    const val REVIEW = "review/{screeningId}"
    const val TRAVELER_PROFILE = "traveler_profile/{travelerName}"
    const val PRACTICE_WORKFLOW = "practice_workflow"

    fun capture(travelerName: String, documentType: String, nationality: String) =
        "capture/${Uri.encode(travelerName)}/${Uri.encode(documentType)}/${Uri.encode(nationality)}"

    fun workflow(id: String) = "workflow/$id"
    fun review(id: String) = "review/$id"
    fun travelerProfile(name: String) = "traveler_profile/${Uri.encode(name)}"
}

private val SHELL_TAB_ROUTES = mapOf(
    ShellTab.DASHBOARD to Routes.DASHBOARD,
    ShellTab.QUEUE to Routes.QUEUE,
    ShellTab.HISTORY to Routes.HISTORY,
    ShellTab.ALERTS to Routes.ALERTS,
    ShellTab.MORE to Routes.MORE,
)

/** Sequential spotlights over the real, live Dashboard, followed by a
 * hands-on practice run with two dedicated concept spotlights (Detected vs
 * Verified, EXACT vs FUZZY) inside it — see ui/tour/TourEngine.kt and
 * PracticeWorkflowScreen.kt. The tour ends after the FUZZY spotlight (the
 * last step here); the officer then finishes the practice run itself with
 * its own Complete-step button, or backs out at any point. */
private fun buildTourSteps(navController: androidx.navigation.NavHostController): List<TourStep> = listOf(
    TourStep(
        id = "bottom_nav",
        anchorId = "bottom_nav",
        title = "Navigate the app",
        body = "Use these tabs to move between your Dashboard, Screening Queue, History, and Alerts.",
    ),
    TourStep(
        id = "new_screening",
        anchorId = "new_screening_button",
        title = "Start a new screening",
        body = "Tap here whenever a traveler arrives at your checkpoint.",
    ),
    TourStep(
        id = "stat_cards",
        anchorId = "stat_cards",
        title = "Your daily numbers",
        body = "These update in real time from your actual screenings today — nothing here is a placeholder.",
    ),
    TourStep(
        id = "risk_overview",
        anchorId = "risk_overview",
        title = "Risk at a glance",
        body = "See how many pending cases are low, medium, or high risk.",
    ),
    TourStep(
        id = "practice_intro",
        title = "Try a practice screening",
        body = "Next, let's walk through a full screening using sample data — nothing you do in practice mode is saved.",
        ctaLabel = "Start practice",
        onCta = {
            navController.navigate(Routes.PRACTICE_WORKFLOW)
            TourState.next()
        },
    ),
    TourStep(
        id = "detected_example",
        anchorId = "detected_example",
        title = "\"Detected\" ≠ \"Verified\"",
        body = "OCR found this field on the document image. That's all \"Detected\" means — nothing has confirmed it yet.",
    ),
    TourStep(
        id = "verified_example",
        anchorId = "verified_example",
        title = "This one is actually verified",
        body = "The backend's validation engine ran a real checksum here and confirmed it. That's the difference from \"Detected.\"",
    ),
    TourStep(
        id = "exact_tag_example",
        anchorId = "exact_tag_example",
        title = "EXACT match",
        body = "This ties to the traveler's actual document number — a confirmed hit against the registry.",
    ),
    TourStep(
        id = "fuzzy_tag_example",
        anchorId = "fuzzy_tag_example",
        title = "FUZZY match",
        body = "This is only a name similarity, not a document-number match. Always apply officer judgment — never treat it the same as an EXACT hit.",
    ),
)

@Composable
fun BorderShieldNavHost(repository: ScreeningRepository) {
    val navController = rememberNavController()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val tourPrefs = remember(context) { TourPreferences.getInstance(context) }

    fun goToTab(tab: ShellTab) {
        navController.navigate(SHELL_TAB_ROUTES.getValue(tab)) {
            popUpTo(Routes.DASHBOARD) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun launchTour() {
        TourState.start(
            steps = buildTourSteps(navController),
            onFinished = {
                AuthSession.username?.let { tourPrefs.markTourSeen(it) }
                scope.launch { repository.logTourCompleted() }
            },
        )
    }

    fun expireSession() {
        if (!AuthSession.isLoggedIn()) return
        scope.launch { repository.logout() }
        navController.navigate(Routes.LOGIN) { popUpTo(0) }
    }

    SessionTimeoutMonitor(onSessionExpired = { expireSession() }) {
    NavHost(navController = navController, startDestination = Routes.LOGIN) {
        composable(Routes.LOGIN) {
            LoginScreen(
                repository = repository,
                onLoggedIn = {
                    navController.navigate(Routes.DASHBOARD) { popUpTo(Routes.LOGIN) { inclusive = true } }
                    val username = AuthSession.username
                    // First successful login for this officer only — never
                    // forced on a returning officer.
                    if (username != null && !tourPrefs.hasSeenTour(username)) {
                        launchTour()
                    }
                },
            )
        }

        composable(Routes.DASHBOARD) {
            val alertCount by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
            AppShell(
                title = stringResource(R.string.nav_dashboard),
                selectedTab = ShellTab.DASHBOARD,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                alertCount = alertCount.size,
            ) { padding ->
                DashboardScreen(
                    repository = repository,
                    padding = padding,
                    onNewScreening = { navController.navigate(Routes.NEW_SCREENING) },
                    onOpenScreening = { id -> navController.navigate(Routes.review(id)) },
                    onViewQueue = { goToTab(ShellTab.QUEUE) },
                    onViewHistory = { goToTab(ShellTab.HISTORY) },
                    onViewAnalytics = { navController.navigate(Routes.ANALYTICS) },
                )
            }
        }

        composable(Routes.QUEUE) {
            val alertCount by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
            AppShell(
                title = stringResource(R.string.nav_queue),
                selectedTab = ShellTab.QUEUE,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                alertCount = alertCount.size,
            ) { padding ->
                QueueScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.HISTORY) {
            val alertCount by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
            AppShell(
                title = stringResource(R.string.nav_history),
                selectedTab = ShellTab.HISTORY,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                alertCount = alertCount.size,
            ) { padding ->
                HistoryScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.ALERTS) {
            val alertCount by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
            AppShell(
                title = stringResource(R.string.nav_alerts),
                selectedTab = ShellTab.ALERTS,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                alertCount = alertCount.size,
            ) { padding ->
                AlertsScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.MORE) {
            val alertCount by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
            AppShell(
                title = stringResource(R.string.nav_more),
                selectedTab = ShellTab.MORE,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                alertCount = alertCount.size,
            ) { padding ->
                MoreScreen(
                    padding = padding,
                    role = AuthSession.role,
                    onOpenAnalytics = { navController.navigate(Routes.ANALYTICS) },
                    onOpenAuditLog = { navController.navigate(Routes.AUDIT_LOG) },
                    onOpenOfficerProfile = { navController.navigate(Routes.OFFICER_PROFILE) },
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                    onLogout = {
                        navController.navigate(Routes.LOGIN) { popUpTo(0) }
                    },
                )
            }
        }

        composable(Routes.ANALYTICS) {
            AnalyticsScreen(repository = repository, onBack = { navController.popBackStack() })
        }
        composable(Routes.AUDIT_LOG) {
            AuditLogScreen(repository = repository, onBack = { navController.popBackStack() })
        }
        composable(Routes.OFFICER_PROFILE) {
            OfficerProfileScreen(
                repository = repository,
                onBack = { navController.popBackStack() },
                onLogout = {
                    navController.navigate(Routes.LOGIN) { popUpTo(0) }
                },
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(repository = repository, onBack = { navController.popBackStack() })
        }

        composable(Routes.NEW_SCREENING) {
            NewScreeningScreen(
                onContinue = { travelerName, documentType, nationality ->
                    navController.navigate(Routes.capture(travelerName, documentType, nationality))
                },
            )
        }
        composable(
            route = Routes.CAPTURE,
            arguments = listOf(
                navArgument("travelerName") { type = NavType.StringType },
                navArgument("documentType") { type = NavType.StringType },
                navArgument("nationality") { type = NavType.StringType },
            ),
        ) { backStackEntry ->
            val args = backStackEntry.arguments
            CaptureScreen(
                repository = repository,
                travelerName = args?.getString("travelerName").orEmpty(),
                documentType = args?.getString("documentType").orEmpty(),
                nationality = args?.getString("nationality").orEmpty(),
                onSubmitted = { screeningId ->
                    navController.navigate(Routes.workflow(screeningId)) { popUpTo(Routes.DASHBOARD) }
                },
            )
        }
        composable(
            route = Routes.WORKFLOW,
            arguments = listOf(navArgument("screeningId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getString("screeningId")
            if (id != null) {
                WorkflowResultScreen(
                    repository = repository,
                    screeningId = id,
                    onComplete = { goToTab(ShellTab.QUEUE) },
                )
            }
        }
        composable(
            route = Routes.REVIEW,
            arguments = listOf(navArgument("screeningId") { type = NavType.StringType }),
        ) { backStackEntry ->
            val id = backStackEntry.arguments?.getString("screeningId")
            if (id != null) {
                ReviewScreen(repository = repository, screeningId = id, onBack = { navController.popBackStack() })
            }
        }
        composable(
            route = Routes.TRAVELER_PROFILE,
            arguments = listOf(navArgument("travelerName") { type = NavType.StringType }),
        ) { backStackEntry ->
            val name = backStackEntry.arguments?.getString("travelerName")
            if (name != null) {
                TravelerProfileScreen(
                    repository = repository,
                    travelerName = name,
                    onOpenScreening = { id -> navController.navigate(Routes.review(id)) },
                )
            }
        }
        composable(Routes.PRACTICE_WORKFLOW) {
            PracticeWorkflowScreen(onFinished = { navController.popBackStack() })
        }
    }
    TourOverlay()
    }
}
