package ae.kartoshka.gatekeeper

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import ae.kartoshka.gatekeeper.logic.Catalog
import ae.kartoshka.gatekeeper.logic.CoreClient
import ae.kartoshka.gatekeeper.logic.Lexical
import java.util.concurrent.TimeUnit

class GatekeeperApp : Application() {
    lateinit var catalog: Catalog
        private set
    lateinit var lexical: Lexical
        private set
    lateinit var store: Store
        private set
    val core: CoreClient by lazy { CoreClient(BuildConfig.CORE_URL) }

    override fun onCreate() {
        super.onCreate()
        catalog = Catalog.fromJson(assets.open("brands.json").bufferedReader().use { it.readText() })
        lexical = Lexical(catalog)
        store = Store(this)
        if (BuildConfig.DEMO) store.seedDemo()
        Appearance.applyAtStart(store)
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL_ALERTS, getString(R.string.channel_alerts), NotificationManager.IMPORTANCE_HIGH)
        )
        // WorkManager's shortest period is 15 minutes; the link handler also syncs when the list is older than that.
        val work = WorkManager.getInstance(this)
        work.enqueueUniquePeriodicWork("blocklist", ExistingPeriodicWorkPolicy.KEEP,
            PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES).build())
        work.enqueue(OneTimeWorkRequestBuilder<SyncWorker>().build())
    }

    companion object {
        const val CHANNEL_ALERTS = "alerts"
    }
}
