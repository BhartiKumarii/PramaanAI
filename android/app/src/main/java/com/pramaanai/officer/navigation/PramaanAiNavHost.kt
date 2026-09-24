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
import com.pramaanai.officer.ui.analytics.AnalyticsScreen
import com.pramaanai.officer.ui.audit.AuditLogScreen
import com.pramaanai.officer.ui.auth.LoginScreen
import com.pramaanai.officer.ui.dashboard.DashboardScreen
import com.pramaanai.officer.ui.more.MoreScreen
import com.pramaanai.officer.ui.profile.OfficerProfileScreen
import com.pramaanai.officer.ui.review.ReviewScreen
import com.pramaanai.officer.ui.settings.SettingsScreen
import com.pramaanai.officer.ui.shell.AppShell
import com.pramaanai.officer.ui.shell.ShellTab
import com.pramaanai.officer.ui.splash.SplashScreen
import com.pramaanai.officer.ui.traveler.TravelerProfileScreen

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
    const val REVIEW = "review/{screeningId}"
    const val TRAVELER_PROFILE = "traveler_profile/{travelerName}"
    const val PRACTICE_WORKFLOW = "practice_workflow"
    const val DOC_VERIFY = "doc_verify"
    const val VERIFICATION_DETAIL = "verification/{verificationId}"
    fun verification(id: String) = "verification/$id"

    fun review(id: String) = "review/$id"
    fun travelerProfile(name: String) = "traveler_profile/${Uri.encode(name)}"
}

private val SHELL_TAB_ROUTES = mapOf(
    ShellTab.DASHBOARD to Routes.DASHBOARD,
    ShellTab.VERIFY to Routes.DOC_VERIFY,
    ShellTab.QUEUE to Routes.QUEUE,
    ShellTab.HISTORY to Routes.HISTORY,
    ShellTab.MORE to Routes.MORE,
)

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
        id = "verify_document",
        anchorId = "verify_document_button",
        title = ctx.getString(R.string.tour_verify_document_title),
        body = ctx.getString(R.string.tour_verify_document_body),
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
        id = "activity_chart",
        anchorId = "activity_chart",
        title = ctx.getString(R.string.tour_activity_title),
        body = ctx.getString(R.string.tour_activity_body),
    ),
    TourStep(
        id = "status_bar",
        anchorId = "status_bar",
        title = ctx.getString(R.string.tour_status_title),
        body = ctx.getString(R.string.tour_status_body),
    ),
    TourStep(
        id = "notifications_bell",
        anchorId = "notifications_bell",
        title = ctx.getString(R.string.tour_bell_title),
        body = ctx.getString(R.string.tour_bell_body),
    ),
    TourStep(
        id = "verify_flow",
        title = ctx.getString(R.string.tour_flow_title),
        body = ctx.getString(R.string.tour_flow_body),
        ctaLabel = ctx.getString(R.string.tour_flow_cta),
        onCta = {
            navController.navigate(Routes.DOC_VERIFY) { popUpTo(Routes.DASHBOARD); launchSingleTop = true }
            com.pramaanai.officer.ui.tour.VerifyPractice.start()
            TourState.next()
        },
    ),
) + buildVerifyPracticeSteps(ctx)

/** The practice verification: the real Verify screens on a bundled synthetic
 * sample (VerifyPractice), one spotlight per part of the workflow. */
private fun buildVerifyPracticeSteps(ctx: android.content.Context): List<TourStep> {
    val p = com.pramaanai.officer.ui.tour.VerifyPractice
    fun step(id: String, titleRes: Int, bodyRes: Int, cta: Int = 0, action: (() -> Unit)? = null) = TourStep(
        id = id, anchorId = id, title = ctx.getString(titleRes), body = ctx.getString(bodyRes),
        ctaLabel = if (cta != 0) ctx.getString(cta) else null,
        onCta = action?.let { a -> { a(); TourState.next() } })
    return listOf(
        step("vp_capture_frame", R.string.tour_vp_capture_frame_title, R.string.tour_vp_capture_frame_body),
        step("vp_capture_buttons", R.string.tour_vp_capture_buttons_title, R.string.tour_vp_capture_buttons_body,
            R.string.tour_vp_use_sample) { p.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.LOAD_DOCUMENT },
        step("vp_regions", R.string.tour_vp_regions_title, R.string.tour_vp_regions_body),
        step("vp_text", R.string.tour_vp_text_title, R.string.tour_vp_text_body),
        step("vp_crossing", R.string.tour_vp_crossing_title, R.string.tour_vp_crossing_body),
        step("vp_continue", R.string.tour_vp_continue_title, R.string.tour_vp_continue_body,
            R.string.tour_vp_to_face) { p.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.TO_FACE },
        step("vp_face_camera", R.string.tour_vp_face_camera_title, R.string.tour_vp_face_camera_body,
            R.string.tour_vp_use_face) { p.command = com.pramaanai.officer.ui.tour.VerifyPractice.Command.USE_FACE },
        step("vp_result_headline", R.string.tour_vp_result_headline_title, R.string.tour_vp_result_headline_body),
        step("vp_decision", R.string.tour_vp_decision_title, R.string.tour_vp_decision_body),
        step("vp_document_problems", R.string.tour_vp_document_problems_title, R.string.tour_vp_document_problems_body),
        step("vp_fields", R.string.tour_vp_fields_title, R.string.tour_vp_fields_body),
        step("vp_face_match", R.string.tour_vp_face_match_title, R.string.tour_vp_face_match_body),
        step("vp_identity", R.string.tour_vp_identity_title, R.string.tour_vp_identity_body),
        step("vp_checks", R.string.tour_vp_checks_title, R.string.tour_vp_checks_body),
        TourStep(id = "vp_done", title = ctx.getString(R.string.tour_vp_done_title), body = ctx.getString(R.string.tour_vp_done_body),
            ctaLabel = ctx.getString(R.string.tour_vp_finish), onCta = { p.stop(); TourState.next() }),
    )
}


@Composable
fun PramaanAiNavHost(repository: ScreeningRepository) {
    val navController = rememberNavController()
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val tourPrefs = remember(context) { TourPreferences.getInstance(context) }
    val readAlertsStore = remember(context) { ReadAlertsStore.getInstance(context) }
    val allAlerts by repository.observeAlerts().collectAsStateWithLifecycle(initialValue = emptyList())
    val readIds by readAlertsStore.readIds.collectAsStateWithLifecycle()
    @Suppress("UNUSED_VARIABLE") val legacyUnread = allAlerts.count { it.id !in readIds }
    // Bell badge: reviewing-officer responses this phone has not shown yet.
    var unreadAlertCount by remember { mutableStateOf(0) }
    LaunchedEffect(Unit) {
        val docRepo = com.pramaanai.officer.data.docverify.DocVerifyRepository(context.applicationContext)
        while (true) {
            val every = com.pramaanai.officer.data.local.AppSettings.responsePollSeconds(context)
            if (every > 0 && AuthSession.isLoggedIn()) docRepo.listMine().onSuccess {
                unreadAlertCount = com.pramaanai.officer.ui.verifications.ResponseTracker.unseenCount(context, it)
            }
            delay((if (every > 0) every else 60) * 1000L)
        }
    }

    // Real, live connectivity — polled, never assumed (see CLAUDE.md).
    // Hoisted once here since AppShell is the shared chrome for every
    // top-level tab; each screen below just displays whatever this
    // reports, it never computes its own status.
    val connectivityMonitor = remember(context) { ConnectivityMonitor(context, RetrofitClient.apiService) }
    var connectivityState by remember { mutableStateOf(ConnectivityState.OFFLINE) }
    LaunchedEffect(connectivityMonitor) {
        while (true) {
            connectivityState = connectivityMonitor.check()
            delay(10_000L)
        }
    }

    // Tabs always open at their own screen. Saving/restoring each tab's stack
    // re-opened whatever sat on top of it (e.g. History restored with
    // Notifications or a verification detail still open).
    fun goToTab(tab: ShellTab) {
        navController.navigate(SHELL_TAB_ROUTES.getValue(tab)) {
            popUpTo(Routes.DASHBOARD)
            launchSingleTop = true
        }
    }

    fun openNotifications() {
        navController.navigate(Routes.ALERTS) {
            popUpTo(Routes.DASHBOARD)
            launchSingleTop = true
        }
    }

    fun launchVerifyTour() {
        navController.navigate(Routes.DOC_VERIFY) { popUpTo(Routes.DASHBOARD); launchSingleTop = true }
        com.pramaanai.officer.ui.tour.VerifyPractice.start()
        TourState.start(steps = buildVerifyPracticeSteps(context),
            onFinished = { com.pramaanai.officer.ui.tour.VerifyPractice.stop() })
    }

    fun launchTour() {
        TourState.start(
            steps = buildTourSteps(context, navController),
            onFinished = {
                com.pramaanai.officer.ui.tour.VerifyPractice.stop()
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
                onAlertsClick = { openNotifications() },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                DashboardScreen(
                    repository = repository,
                    padding = padding,
                    onVerifyDocument = { goToTab(ShellTab.VERIFY) },
                    onOpenScreening = { id -> navController.navigate(Routes.verification(id)) },
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
                onAlertsClick = { openNotifications() },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                com.pramaanai.officer.ui.verifications.VerificationListScreen(padding, com.pramaanai.officer.ui.verifications.ListMode.REVIEW,
                    onOpen = { id -> navController.navigate(Routes.verification(id)) })
            }
        }

        composable(Routes.HISTORY) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_history),
                selectedTab = ShellTab.HISTORY,
                onTabSelected = { goToTab(it) },
                onAlertsClick = { openNotifications() },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                com.pramaanai.officer.ui.verifications.VerificationListScreen(padding, com.pramaanai.officer.ui.verifications.ListMode.HISTORY,
                    onOpen = { id -> navController.navigate(Routes.verification(id)) })
            }
        }

        composable(Routes.MORE) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.nav_more),
                selectedTab = ShellTab.MORE,
                onTabSelected = { goToTab(it) },
                onAlertsClick = { openNotifications() },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                MoreScreen(
                    padding = padding,
                    role = AuthSession.role,
                    onOpenAnalytics = { navController.navigate(Routes.ANALYTICS) },
                    onOpenDocVerify = { goToTab(ShellTab.VERIFY) },
                    onOpenAuditLog = { navController.navigate(Routes.AUDIT_LOG) },
                    onOpenOfficerProfile = { navController.navigate(Routes.OFFICER_PROFILE) },
                    onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                    onLogout = {
                        navigateToLogin()
                    },
                )
            }
        }

        composable(Routes.DOC_VERIFY) {
            AppShell(
                connectivityState = connectivityState,
                title = stringResource(R.string.more_doc_verify),
                selectedTab = ShellTab.VERIFY,
                onTabSelected = { goToTab(it) },
                onAlertsClick = { openNotifications() },
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchVerifyTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                com.pramaanai.officer.ui.docverify.DocVerifyScreen(padding = padding)
            }
        }

        composable(Routes.ALERTS) {
            AppShell(
                connectivityState = connectivityState,
                title = "Notifications",
                selectedTab = ShellTab.QUEUE,
                onTabSelected = { goToTab(it) },
                onAlertsClick = {},
                onProfileClick = { navController.navigate(Routes.OFFICER_PROFILE) },
                onHelpClick = { launchTour() },
                officerName = AuthSession.username,
                alertCount = unreadAlertCount,
            ) { padding ->
                com.pramaanai.officer.ui.verifications.VerificationListScreen(padding, com.pramaanai.officer.ui.verifications.ListMode.NOTIFICATIONS,
                    onOpen = { id -> navController.navigate(Routes.verification(id)) })
            }
        }
        composable(
            route = Routes.VERIFICATION_DETAIL,
            arguments = listOf(navArgument("verificationId") { type = NavType.StringType }),
        ) { entry ->
            entry.arguments?.getString("verificationId")?.let { id ->
                com.pramaanai.officer.ui.verifications.VerificationDetailScreen(id, onBack = { navController.popBackStack() })
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
                onReplayTour = { navController.navigate(Routes.DASHBOARD) { popUpTo(Routes.DASHBOARD) { inclusive = true } }; launchTour() },
                onLogout = {
                    navigateToLogin()
                },
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(repository = repository, onBack = { navController.popBackStack() })
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
