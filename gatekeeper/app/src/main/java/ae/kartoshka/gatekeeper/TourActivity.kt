package ae.kartoshka.gatekeeper

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.WindowManager
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * Product tour for recording the phone screen: the same scripted 24 s animation as /showcase on the web,
 * full screen with the system bars hidden and the screen kept on. It plays from the copy built into the APK
 * (make tour), so it needs no network; without that copy it opens /showcase?phone on the resident server.
 * Tap pauses. Open it with a long press on the app icon (Product tour), a long press on the Home title, or
 * adb shell am start -n ae.kartoshka.gatekeeper/.TourActivity --es lang ar.
 */
class TourActivity : AppCompatActivity() {
    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
        val lang = intent.getStringExtra(EXTRA_LANG)?.takeIf { it == "ar" || it == "en" } ?: Appearance.webLanguage(this)
        val web = WebView(this).apply {
            setBackgroundColor(Color.parseColor("#0b1320"))
            settings.javaScriptEnabled = true
            webViewClient = WebViewClient()
        }
        setContentView(web)
        // record: wait on the first frame for a tap, then play once and hold the end card (make record-tour).
        val options = "lang=$lang" + if (intent.getBooleanExtra(EXTRA_RECORD, false)) "&paused&once" else ""
        web.loadUrl(if (bundled()) "file:///android_asset/tour/index.html#$options" else BuildConfig.RESIDENT_URL.trimEnd('/') + "/showcase?phone&$options")
    }

    private fun bundled() = runCatching { assets.open("tour/tour.js").close() }.isSuccess

    companion object {
        const val EXTRA_LANG = "lang"
        const val EXTRA_RECORD = "record"

        fun open(context: Context) = context.startActivity(Intent(context, TourActivity::class.java))
    }
}
