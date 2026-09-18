package com.bordershield.officer

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.lifecycleScope
import com.bordershield.officer.data.CHECKPOINT
import com.bordershield.officer.data.ScreeningRepository
import com.bordershield.officer.data.local.AuditLogStore
import com.bordershield.officer.data.local.LocalScreeningStore
import com.bordershield.officer.data.local.LocaleManager
import com.bordershield.officer.data.remote.RetrofitClient
import com.bordershield.officer.navigation.BorderShieldNavHost
import com.bordershield.officer.ui.theme.BorderShieldOfficerTheme
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

        val store = LocalScreeningStore.getInstance(applicationContext)
        val auditLog = AuditLogStore.getInstance(applicationContext)
        val imagesDir = java.io.File(applicationContext.filesDir, "images").apply { mkdirs() }
        val repository = ScreeningRepository(store, auditLog, RetrofitClient.apiService, imagesDir, CHECKPOINT)

        lifecycleScope.launch { repository.seedMockDataIfEmpty() }

        setContent {
            BorderShieldOfficerTheme {
                BorderShieldNavHost(repository = repository)
            }
        }
    }
}
