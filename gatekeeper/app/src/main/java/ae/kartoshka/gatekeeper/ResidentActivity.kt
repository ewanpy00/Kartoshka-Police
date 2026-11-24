package ae.kartoshka.gatekeeper

import android.annotation.SuppressLint
import android.net.Uri
import android.os.Bundle
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity

/**
 * The resident screens (Link X-ray, safe preview, My reports, scam radar, SMS paste: section 3.1) in a
 * WebView. Only the resident origin loads inside; any other link (the official service button) goes to the
 * real browser. Reports made from the native block page are copied into the screens' storage on load.
 */
class ResidentActivity : AppCompatActivity() {
    private val origin by lazy { Uri.parse(BuildConfig.RESIDENT_URL) }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val web = WebView(this)
        setContentView(web)
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = false
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val target = request.url
                if (target.scheme == origin.scheme && target.authority == origin.authority) return false
                if (target.scheme == "http" || target.scheme == "https") Browsers.open(this@ResidentActivity, target.toString())
                return true
            }

            override fun onPageFinished(view: WebView, url: String) {
                val native = (application as GatekeeperApp).store.reportsJson()
                view.evaluateJavascript(MERGE_REPORTS.replace("NATIVE", native), null)
            }
        }
        web.loadUrl(BuildConfig.RESIDENT_URL.trimEnd('/') + (intent.getStringExtra(EXTRA_PATH) ?: "/"))
    }

    companion object {
        const val EXTRA_PATH = "path"

        fun checkPath(url: String) = "/check?source=gatekeeper&url=" + Uri.encode(url)
        fun smsPath(text: String) = "/check?source=share&text=" + Uri.encode(text.take(4000))

        // Adds native reports missing from localStorage, then reloads once so the page lists them.
        private const val MERGE_REPORTS = """(function(){try{var k='kp.reports';var have=JSON.parse(localStorage.getItem(k)||'[]');
var ids={};have.forEach(function(r){ids[r.id]=1});var add=NATIVE.filter(function(r){return r.id&&!ids[r.id]});
if(add.length){localStorage.setItem(k,JSON.stringify(add.concat(have).slice(0,50)));location.reload();}}catch(e){}})()"""
    }
}
