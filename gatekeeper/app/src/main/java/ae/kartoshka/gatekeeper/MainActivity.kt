package ae.kartoshka.gatekeeper

import android.Manifest
import android.app.role.RoleManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.format.DateUtils
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity

/**
 * Home: protection setup (default browser, Private DNS, which browser links go to) and the resident
 * screens. No account and no sign-in.
 */
class MainActivity : AppCompatActivity() {
    private val app get() = application as GatekeeperApp

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        if (Build.VERSION.SDK_INT >= 33) requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)

        findViewById<Button>(R.id.set_default).setOnClickListener { askDefaultBrowser() }
        findViewById<Button>(R.id.set_dns).setOnClickListener { openPrivateDns() }
        findViewById<Button>(R.id.pick_browser).setOnClickListener { pickBrowser() }
        mapOf(R.id.open_check to "/check", R.id.open_sms to "/sms", R.id.open_reports to "/reports", R.id.open_radar to "/radar")
            .forEach { (id, path) ->
                findViewById<Button>(id).setOnClickListener {
                    startActivity(Intent(this, ResidentActivity::class.java).putExtra(ResidentActivity.EXTRA_PATH, path))
                }
            }
    }

    override fun onResume() {
        super.onResume()
        val isDefault = Build.VERSION.SDK_INT >= 29 && getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_BROWSER)
        findViewById<TextView>(R.id.default_state).setText(if (isDefault) R.string.default_on else R.string.default_off)
        findViewById<Button>(R.id.set_default).isEnabled = !isDefault
        val browser = Browsers.target(this)
        findViewById<TextView>(R.id.browser_state).text = getString(R.string.forward_to,
            Browsers.installed(this).firstOrNull { it.first == browser }?.second ?: getString(R.string.none))
        val synced = app.store.syncedAt
        findViewById<TextView>(R.id.list_state).text = getString(R.string.list_state, app.store.blockedCount,
            if (synced == 0L) getString(R.string.never) else DateUtils.getRelativeTimeSpanString(synced).toString())
    }

    private fun askDefaultBrowser() {
        if (Build.VERSION.SDK_INT >= 29) {
            val roles = getSystemService(RoleManager::class.java)
            if (roles.isRoleAvailable(RoleManager.ROLE_BROWSER)) {
                @Suppress("DEPRECATION")
                startActivityForResult(roles.createRequestRoleIntent(RoleManager.ROLE_BROWSER), 2)
                return
            }
        }
        startActivity(Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS))
    }

    /** Android has no API to set Private DNS for the user: copy the hostname and open the network settings. */
    private fun openPrivateDns() {
        val host = BuildConfig.DNS_HOST
        if (host.isBlank()) {
            Toast.makeText(this, R.string.dns_not_configured, Toast.LENGTH_LONG).show()
            return
        }
        getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("Private DNS", host))
        Toast.makeText(this, getString(R.string.dns_copied, host), Toast.LENGTH_LONG).show()
        startActivity(Intent(Settings.ACTION_WIRELESS_SETTINGS))
    }

    private fun pickBrowser() {
        val all = Browsers.installed(this)
        if (all.isEmpty()) {
            Toast.makeText(this, R.string.no_browser, Toast.LENGTH_LONG).show()
            return
        }
        AlertDialog.Builder(this)
            .setTitle(R.string.pick_browser)
            .setItems(all.map { it.second }.toTypedArray()) { _, which ->
                app.store.browser = all[which].first
                onResume()
            }
            .show()
    }
}
