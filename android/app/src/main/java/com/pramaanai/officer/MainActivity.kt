package com.pramaanai.officer

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.lifecycleScope
import com.pramaanai.officer.data.CHECKPOINT
import com.pramaanai.officer.data.ScreeningRepository
import com.pramaanai.officer.data.local.AuditLogStore
import com.pramaanai.officer.data.local.LocalScreeningStore
import com.pramaanai.officer.data.local.LocaleManager
import com.pramaanai.officer.data.local.PendingSubmissionQueue
import com.pramaanai.officer.data.remote.RetrofitClient
import com.pramaanai.officer.data.sync.PendingSubmissionWorker
import com.pramaanai.officer.navigation.PramaanAiNavHost
import com.pramaanai.officer.ui.theme.PramaanAiTheme
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    // Applies the officer's saved language preference at the Context level
    // (not just inside Compose) so it also covers anything reading
    // resources outside the composition — recreate() after a change in
    // Settings re-runs this with the new tag.
    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleManager.wrap(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Resume a previously signed-in officer without retyping credentials.
        com.pramaanai.officer.data.local.SessionStore.init(applicationContext)
        com.pramaanai.officer.data.remote.AuthSession.restore()

        val store = LocalScreeningStore.getInstance(applicationContext)
        val auditLog = AuditLogStore.getInstance(applicationContext)
        val pendingQueue = PendingSubmissionQueue.getInstance(applicationContext)
        val imagesDir = java.io.File(applicationContext.filesDir, "images").apply { mkdirs() }
        val repository = ScreeningRepository(store, auditLog, RetrofitClient.apiService, imagesDir, CHECKPOINT, pendingQueue)

        lifecycleScope.launch { repository.seedMockDataIfEmpty() }
        // Drain anything left queued from a previous session as soon as
        // WorkManager sees a connected network.
        PendingSubmissionWorker.enqueue(applicationContext)
        com.pramaanai.officer.data.docverify.DocVerifySyncWorker.enqueue(applicationContext)

        setContent {
            PramaanAiTheme {
                PramaanAiNavHost(repository = repository)
            }
        }
    }
}
