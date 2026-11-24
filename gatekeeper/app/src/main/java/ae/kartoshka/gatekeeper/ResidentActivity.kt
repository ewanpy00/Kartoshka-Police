package ae.kartoshka.gatekeeper

import android.os.Bundle
import android.webkit.WebView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.appbar.MaterialToolbar

/** A resident screen on its own (Details from the block page, the scam notification). */
class ResidentActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_resident)
        val web = findViewById<WebView>(R.id.web)
        val error = findViewById<android.view.View>(R.id.web_error)
        ResidentWeb.setup(this, web, findViewById(R.id.web_progress), error, error.findViewById(R.id.retry))
        val path = intent.getStringExtra(EXTRA_PATH) ?: "/"
        findViewById<MaterialToolbar>(R.id.toolbar).apply {
            title = getString(titleFor(path))
            setNavigationOnClickListener { finish() }
        }
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() = if (web.canGoBack()) web.goBack() else finish()
        })
        web.loadUrl(ResidentWeb.url(this, path))
    }

    private fun titleFor(path: String) = when {
        path.startsWith("/reports") -> R.string.action_reports
        path.startsWith("/radar") -> R.string.action_radar
        path.startsWith("/sms") -> R.string.action_sms
        else -> R.string.action_check
    }

    companion object {
        const val EXTRA_PATH = "path"

        fun checkPath(url: String) = ResidentWeb.checkPath(url)
        fun smsPath(text: String) = ResidentWeb.smsPath(text)
    }
}
