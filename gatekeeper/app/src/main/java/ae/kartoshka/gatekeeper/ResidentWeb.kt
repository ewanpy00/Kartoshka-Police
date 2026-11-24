package ae.kartoshka.gatekeeper

import android.annotation.SuppressLint
import android.app.Activity
import android.graphics.Bitmap
import android.net.Uri
import android.view.View
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * The resident screens (Link X-ray, safe preview, My reports, scam radar, SMS paste: section 3.1) inside a
 * WebView. Only the resident origin loads inside; other links (the official service button) go to the real
 * browser. The user agent carries "KartoshkaGatekeeper", so the pages hide their own header and tabs and
 * follow the phone's language. Reports made on the native block page are copied into the pages' storage.
 */
object ResidentWeb {
    private val origin: Uri by lazy { Uri.parse(BuildConfig.RESIDENT_URL) }

    /** The page URL with the app's resolved language and theme, so the page matches the native screens. */
    fun url(context: android.content.Context, path: String): String {
        val join = if (path.contains('?')) "&" else "?"
        return BuildConfig.RESIDENT_URL.trimEnd('/') + path + join +
            "lang=" + Appearance.webLanguage(context) + "&theme=" + Appearance.webTheme(context)
    }

    fun checkPath(url: String) = "/check?source=gatekeeper&url=" + Uri.encode(url)
    fun smsPath(text: String) = "/check?source=share&text=" + Uri.encode(text.take(4000))

    @SuppressLint("SetJavaScriptEnabled")
    fun setup(activity: Activity, web: WebView, progress: View, error: View, retry: View) {
        web.settings.javaScriptEnabled = true
        web.settings.domStorageEnabled = true
        web.settings.allowFileAccess = false
        web.settings.userAgentString = web.settings.userAgentString + " KartoshkaGatekeeper/" + BuildConfig.VERSION_NAME
        web.setBackgroundColor(activity.getColor(R.color.page))
        var failed = false
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val target = request.url
                if (target.scheme == origin.scheme && target.authority == origin.authority) return false
                if (target.scheme == "http" || target.scheme == "https") Browsers.open(activity, target.toString())
                return true
            }

            override fun onPageStarted(view: WebView, url: String, favicon: Bitmap?) {
                failed = false
                progress.visibility = View.VISIBLE
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, err: WebResourceError) {
                if (request.isForMainFrame) {
                    failed = true
                    error.visibility = View.VISIBLE
                }
            }

            override fun onPageFinished(view: WebView, url: String) {
                progress.visibility = View.GONE
                if (failed) return
                error.visibility = View.GONE
                val native = (activity.application as GatekeeperApp).store.reportsJson()
                view.evaluateJavascript(MERGE_REPORTS.replace("NATIVE", native), null)
            }
        }
        retry.setOnClickListener {
            error.visibility = View.GONE
            web.reload()
        }
    }

    // Adds native reports missing from localStorage, then reloads once so the page lists them.
    private const val MERGE_REPORTS = """(function(){try{var k='kp.reports';var have=JSON.parse(localStorage.getItem(k)||'[]');
var ids={};have.forEach(function(r){ids[r.id]=1});var add=NATIVE.filter(function(r){return r.id&&!ids[r.id]});
if(add.length){localStorage.setItem(k,JSON.stringify(add.concat(have).slice(0,50)));location.reload();}}catch(e){}})()"""
}
