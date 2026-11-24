package ae.kartoshka.gatekeeper

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri

/**
 * Forwarding to the user's real browser with an explicit intent, so the link never loops back into
 * Gatekeeper (which is the default browser).
 */
object Browsers {
    private val PREFERRED = listOf("com.android.chrome", "com.sec.android.app.sbrowser", "org.mozilla.firefox",
        "com.microsoft.emmx", "com.brave.browser", "com.opera.browser")

    fun installed(context: Context): List<Pair<String, String>> {
        val probe = Intent(Intent.ACTION_VIEW, Uri.parse("https://example.com/")).addCategory(Intent.CATEGORY_BROWSABLE)
        val pm = context.packageManager
        return pm.queryIntentActivities(probe, PackageManager.MATCH_ALL)
            .map { it.activityInfo.packageName to it.loadLabel(pm).toString() }
            .filter { it.first != context.packageName }
            .distinctBy { it.first }
    }

    fun target(context: Context): String? {
        val all = installed(context).map { it.first }
        val chosen = (context.applicationContext as GatekeeperApp).store.browser
        return chosen?.takeIf { it in all } ?: PREFERRED.firstOrNull { it in all } ?: all.firstOrNull()
    }

    /** Opens [url] outside Gatekeeper. False when no other browser is installed. */
    fun open(context: Context, url: String): Boolean {
        val pkg = target(context) ?: return false
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            .addCategory(Intent.CATEGORY_BROWSABLE)
            .setPackage(pkg)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try { context.startActivity(intent); true } catch (e: Exception) { false }
    }
}
