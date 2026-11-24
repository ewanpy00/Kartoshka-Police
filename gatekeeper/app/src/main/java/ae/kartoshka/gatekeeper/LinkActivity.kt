package ae.kartoshka.gatekeeper

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import ae.kartoshka.gatekeeper.logic.Action
import ae.kartoshka.gatekeeper.logic.Decision
import ae.kartoshka.gatekeeper.logic.Links
import ae.kartoshka.gatekeeper.logic.Remote
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Every tapped http(s) link and every shared text lands here (ARCHITECTURE.md section 3):
 * local check, then `POST /v1/check` within 400 ms, then forward, warn, block, or "Checking link…" for up
 * to 3 s. The screen stays blank unless the check has to wait.
 */
class LinkActivity : AppCompatActivity() {
    private val app get() = application as GatekeeperApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_checking)
        val (url, text) = incoming(intent) ?: return finish()
        if (url == null) {
            // Shared text with no link or several links: the resident SMS check handles it.
            startActivity(Intent(this, ResidentActivity::class.java).putExtra(ResidentActivity.EXTRA_PATH, ResidentActivity.smsPath(text)))
            return finish()
        }
        findViewById<TextView>(R.id.checking_host).text = Links.host(url)?.let(Links::unicodeHost) ?: url
        lifecycleScope.launch { handle(url, text) }
    }

    /** (url, text): url is null when shared text holds zero or several links. */
    private fun incoming(intent: Intent): Pair<String?, String>? = when (intent.action) {
        Intent.ACTION_VIEW -> intent.dataString?.let { it to "" }
        Intent.ACTION_SEND -> {
            val text = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty()
            val urls = Links.extract(text)
            if (text.isBlank()) null else (urls.singleOrNull() to text)
        }
        else -> null
    }

    private suspend fun handle(url: String, text: String) {
        val local = app.lexical.score(url)
        val host = Links.host(url)
        val listed = host != null && app.store.listed(host)
        refreshListIfOld()
        if (local.official) return done(Action.Forward, url)

        val first = withContext(Dispatchers.IO) { app.core.check(url, "gatekeeper", text, budgetMs = 400) }
        var action = Decision.decide(url, local, listed, first, app.catalog, text)
        if (action == Action.Checking) {
            findViewById<View>(R.id.checking).visibility = View.VISIBLE
            Motion.pulse(findViewById(R.id.checking_ring))
            Motion.popIn(findViewById(R.id.checking_shield))
            val checkId = (first as? Remote.Answer)?.verdict?.checkId
            val second = withContext(Dispatchers.IO) {
                if (checkId != null) Remote.Answer(runCatching { app.core.get(checkId, 2600) }.getOrElse { return@withContext Remote.Timeout })
                else app.core.check(url, "gatekeeper", text, budgetMs = 2600)
            }
            action = Decision.decide(url, local, listed, second, app.catalog, text)
            if (action == Action.Checking) {
                val id = (second as? Remote.Answer)?.verdict?.checkId ?: checkId
                action = Decision.afterWait(url, local, listed, app.catalog, text, id)
            }
        }
        done(action, url)
    }

    private fun done(action: Action, url: String) {
        when (action) {
            is Action.Forward -> if (!Browsers.open(this, url)) Toast.makeText(this, R.string.no_browser, Toast.LENGTH_LONG).show()
            is Action.Warn -> {
                app.store.addCheck(url, "warn", action.page.brandId?.let { app.catalog.brand(it)?.nameEn })
                startActivity(VerdictActivity.intent(this, action.page, blocked = false))
                if (action.page.deepRunning) action.page.checkId?.let { DeepWatchWorker.start(this, it) }
            }
            is Action.Block -> {
                app.store.countBlock()
                app.store.addCheck(url, "block", action.page.brandId?.let { app.catalog.brand(it)?.nameEn })
                startActivity(VerdictActivity.intent(this, action.page, blocked = true))
            }
            is Action.Checking -> Unit
        }
        finish()
    }

    private fun refreshListIfOld() {
        if (System.currentTimeMillis() - app.store.syncedAt > 15 * 60_000L) {
            WorkManager.getInstance(this).enqueue(OneTimeWorkRequestBuilder<SyncWorker>().build())
        }
    }
}
