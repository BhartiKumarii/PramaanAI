package com.pramaanai.officer.navigation

import android.net.Uri
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.pramaanai.officer.R
import com.pramaanai.officer.data.connectivity.ConnectivityMonitor
import com.pramaanai.officer.data.connectivity.ConnectivityState
import com.pramaanai.officer.data.local.ReadAlertsStore
import com.pramaanai.officer.data.local.TourPreferences
import com.pramaanai.officer.data.remote.RetrofitClient
import kotlinx.coroutines.delay
import com.pramaanai.officer.ui.session.SessionTimeoutMonitor
import com.pramaanai.officer.ui.tour.PracticeWorkflowScreen
import com.pramaanai.officer.ui.tour.TourOverlay
import com.pramaanai.officer.ui.tour.TourState
import com.pramaanai.officer.ui.tour.TourStep
import kotlinx.coroutines.launch
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.remote.AuthSession
import com.pramaanai.officer.data.remote.SessionEvents
import com.pramaanai.officer.ui.alerts.AlertsScreen
import com.pramaanai.officer.ui.analytics.AnalyticsScreen
import com.pramaanai.officer.ui.audit.AuditLogScreen
import com.pramaanai.officer.ui.auth.LoginScreen
import com.pramaanai.officer.ui.capture.CaptureScreen
import com.pramaanai.officer.ui.dashboard.DashboardScreen
import com.pramaanai.officer.ui.history.HistoryScreen
import com.pramaanai.officer.ui.more.MoreScreen
import com.pramaanai.officer.ui.newscreening.NewScreeningScreen
import com.pramaanai.officer.ui.newscreening.ScreeningData
import com.pramaanai.officer.ui.newscreening.DocumentType
import com.pramaanai.officer.ui.profile.OfficerProfileScreen
import com.pramaanai.officer.ui.queue.QueueScreen
import com.pramaanai.officer.ui.review.ReviewScreen
import com.google.gson.Gson
import com.pramaanai.officer.ui.settings.SettingsScreen
import com.pramaanai.officer.ui.shell.AppShell
import com.pramaanai.officer.ui.shell.ShellTab
import com.pramaanai.officer.ui.splash.SplashScreen
import com.pramaanai.officer.ui.traveler.TravelerProfileScreen
import com.pramaanai.officer.ui.workflow.WorkflowResultScreen

object Routes {
    const val SPLASH = "splash"
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
    const val CAPTURE = "capture/{screeningDataJson}"
    const val WORKFLOW = "workflow/{screeningId}"
    const val REVIEW = "review/{screeningId}"
    const val TRAVELER_PROFILE = "traveler_profile/{travelerName}"
    const val PRACTICE_WORKFLOW = "practice_workflow"

    fun workflow(id: String) = "workflow/$id"
    fun review(id: String) = "review/$id"
    fun travelerProfile(name: String) = "traveler_profile/${Uri.encode(name)}"
}

private val gson = Gson()

private val SHELL_TAB_ROUTES = mapOf(
    ShellTab.DASHBOARD to Routes.DASHBOARD,
    ShellTab.QUEUE to Routes.QUEUE,
    ShellTab.HISTORY to Routes.HISTORY,
    ShellTab.ALERTS to Routes.ALERTS,
    ShellTab.MORE to Routes.MORE,
)

private fun getSelectedCheckpointFromAuth(): com.pramaanai.officer.data.remote.CheckpointResponse? {
    val code = com.pramaanai.officer.data.remote.AuthSession.checkpointCode
    val name = com.pramaanai.officer.data.remote.AuthSession.checkpointName
    if (code != null && name != null) {
        return com.pramaanai.officer.data.remote.CheckpointResponse(
            id = "", code = code, name = name, location = null, isActive = true
        )
    }
    return null
}

/** Sequential spotlights over the real, live Dashboard, followed by a
 * hands-on practice run with two dedicated concept spotlights (Detected vs
 * Verified, EXACT vs FUZZY) inside it — see ui/tour/TourEngine.kt and
 * PracticeWorkflowScreen.kt. The tour ends after the FUZZY spotlight (the
 * last step here); the officer then finishes the practice run itself with
 * its own Complete-step button, or backs out at any point. */
private fun buildTourSteps(ctx: android.content.Context, navController: androidx.navigation.NavHostController): List<TourStep> = listOf(
    TourStep(
        id = "bottom_nav",
        anchorId = "bottom_nav",
        title = ctx.getString(R.string.tour_nav_title),
        body = ctx.getString(R.string.tour_nav_body),
    ),
    TourStep(
        id = "new_screening",
        anchorId = "new_screening_button",
        title = ctx.getString(R.string.tour_new_screening_title),
        body = ctx.getString(R.string.tour_new_screening_body),
    ),
    TourStep(
        id = "stat_cards",
        anchorId = "stat_cards",
        title = ctx.getString(R.string.tour_daily_numbers_title),
        body = ctx.getString(R.string.tour_daily_numbers_body),
    ),
    TourStep(
        id = "risk_overview",
        anchorId = "risk_overview",
        title = ctx.getString(R.string.tour_risk_title),
        body = ctx.getString(R.string.tour_risk_body),
    ),
    TourStep(
        id = "practice_intro",
        title = ctx.getString(R.string.tour_practice_title),
        body = ctx.getString(R.string.tour_practice_body),
        ctaLabel = ctx.getString(R.string.tour_practice_cta),
        onCta = {
            navController.navigate(Routes.PRACTICE_WORKFLOW)
            TourState.next()
        },
    ),
    TourStep(
        id = "detected_example",
        anchorId = "detected_example",
        title = ctx.getString(R.string.tour_detected_title),
        body = ctx.getString(R.string.tour_detected_body),
    ),
    TourStep(
        id = "verified_example",
        anchorId = "verified_example",
        title = ctx.getString(R.string.tour_verified_title),
        body = ctx.getString(R.string.tour_verified_body),
    ),
    TourStep(
        id = "exact_tag_example",
        anchorId = "exact_tag_example",
        title = ctx.getString(R.string.tour_exact_title),
        body = ctx.getString(R.string.tour_exact_body),
    ),
    TourStep(
        id = "fuzzy_tag_example",
        anchorId = "fuzzy_tag_example",
        title = ctx.getString(R.string.tour_fuzzy_title),
        body = ctx.getString(R.string.tour_fuzzy_body),
    ),
)

@Composable
fun PramaanAiNavHost(repository: ScreeningRepository) {
    val navController = rememberNavController()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val tourPrefs = remember(context) { TourPreferences.getInstance(context) }
    val readAlertsStore = remember(context) { ReadAlertsStore.getInstance(context) }
    val allAlerts by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
    val readIds by readAlertsStore.readIds.collectAsStateWithLifecycle()
    val unreadAlertCount = allAlerts.count { it.id !in readIds }

    // Real, live connectivity — polled, never assumed (see CLAUDE.md).
    // Hoisted once here since AppShell is the shared chrome for every
    // top-level tab; each screen below just displays whatever this
    // reports, it never computes its own status.
    val connectivityMonitor = remember(context) { ConnectivityMonitor(context, RetrofitClient.apiService) }
    var connectivityState by remember { mutableStateOf(ConnectivityState.OFFLINE) }
    LaunchedEffect(connectivityMonitor) {
        while (true) {
            connectivityState = connectivityMonitor.check()
            delay(15_000L)
        }
    }

    fun goToTab(tab: ShellTab) {
        navController.navigate(SHELL_TAB_ROUTES.getValue(tab)) {
            popUpTo(Routes.DASHBOARD) { saveState = true }
            launchSingleTop = true
            restoreState = true
        }
    }

    fun launchTour() {
        TourState.start(
            steps = buildTourSteps(context, navController),
            onFinished = {
                AuthSession.username?.let { tourPrefs.markTourSeen(it) }
                scope.launch { repository.logTourCompleted() }
            },
        )
    }

    fun navigateToLogin() {
        navController.navigate(Routes.LOGIN) { popUpTo(navController.graph.id) { inclusive = true } }
    }

    fun expireSession() {
        if (!AuthSession.isLoggedIn()) return
        SessionEvents.pendingNotice = context.getString(R.string.session_expired_notice)
        scope.launch { repository.logout() }
        navigateToLogin()
    }

    // A session that ended somewhere deep inside a network call (refresh
    // token rejected/expired) — route back to sign-in from wherever the
    // officer currently is.
    LaunchedEffect(Unit) { SessionEvents.expired.collect { navigateToLogin() } }

    // A session restored from the encrypted store may hold an expired
    // access token — renew it now instead of failing the first real call.
    LaunchedEffect(Unit) { if (AuthSession.isLoggedIn()) repository.refreshSession() }

    val postSplashDestination = remember { if (AuthSession.isLoggedIn()) Routes.DASHBOARD else Routes.LOGIN }
    val startDestination = Routes.SPLASH

    val currentRoute = navController.currentBackStackEntryAsState().value?.destination?.route
    SessionTimeoutMonitor(
        active = currentRoute != null && currentRoute != Routes.LOGIN,
        onSessionExpired = { expireSession() },
        onStaySignedIn = { scope.launch { repository.refreshSession() } },
    ) {
    NavHost(navController = navController, startDestination = startDestination) {
        composable(Routes.SPLASH) {
            SplashScreen(
                onFinished = {
                    navController.navigate(postSplashDestination) {
                        popUpTo(Routes.SPLASH) { inclusive = true }
                    }
                },
            )
        }
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
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_dashboard),
                selectedTab = ShellTab.DASHBOARD,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
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
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_queue),
                selectedTab = ShellTab.QUEUE,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                QueueScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.HISTORY) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_history),
                selectedTab = ShellTab.HISTORY,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                HistoryScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.ALERTS) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_alerts),
                selectedTab = ShellTab.ALERTS,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                AlertsScreen(repository = repository, padding = padding, onOpenScreening = { id -> navController.navigate(Routes.review(id)) })
            }
        }

        composable(Routes.MORE) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_more),
                selectedTab = ShellTab.MORE,
                onTabSelected = { goToTab(it) },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                MoreScreen(
                    padding = padding,
                    role = AuthSession.role,
                    onOpenAnalytics = { navController.navigate(Routes.ANALYTICS) },
                    onOpenAuditLog = { navController.navigate(Routes.AUDIT_LOG) },
                    onOpenOfficerProfile = { navController.navigate(Routes.OFFICER_PROFILE) },
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                    onLogout = {
                        navigateToLogin()
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
                    navigateToLogin()
                },
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(repository = repository, onBack = { navController.popBackStack() })
        }

        composable(Routes.NEW_SCREENING) {
            val selectedCheckpoint = getSelectedCheckpointFromAuth()
            NewScreeningScreen(
                repository = repository,
                selectedCheckpoint = selectedCheckpoint,
                onContinue = { screeningData ->
                    val json = gson.toJson(screeningData)
                    navController.navigate("capture/${Uri.encode(json)}")
                },
            )
        }
        composable(
            route = Routes.CAPTURE,
            arguments = listOf(navArgument("screeningDataJson") { type = NavType.StringType }),
        ) { backStackEntry ->
            val args = backStackEntry.arguments
            val json = args?.getString("screeningDataJson") ?: ""
            val screeningData = if (json.isNotBlank()) {
                try { gson.fromJson(json, ScreeningData::class.java) } catch (_: Exception) {
                    ScreeningData(DocumentType.PASSPORT, null)
                }
            } else {
                ScreeningData(DocumentType.PASSPORT, null)
            }
            CaptureScreen(
                repository = repository,
                documentType = screeningData.documentType.value,
                checkpointCode = screeningData.checkpointCode,
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
