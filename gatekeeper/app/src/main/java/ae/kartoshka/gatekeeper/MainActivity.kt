package ae.kartoshka.gatekeeper

import android.Manifest
import android.animation.ValueAnimator
import android.app.role.RoleManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.content.res.ColorStateList
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.inputmethod.EditorInfo
import android.view.inputmethod.InputMethodManager
import android.text.format.DateUtils
import android.view.View
import android.webkit.WebView
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.widget.NestedScrollView
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import com.google.android.material.bottomnavigation.BottomNavigationView
import com.google.android.material.button.MaterialButton
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.divider.MaterialDivider
import ae.kartoshka.gatekeeper.logic.Links
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout

/**
 * Home and the three resident tabs (Check, Reports, Radar) under one bottom navigation. Home shows the
 * protection status, a box to check a link, the counters, quick actions and the settings (including language
 * and light or dark appearance). No account and no sign-in.
 */
class MainActivity : AppCompatActivity() {
    private val app get() = application as GatekeeperApp
    private lateinit var nav: BottomNavigationView
    private lateinit var home: View
    private lateinit var web: WebView
    private lateinit var webError: View
    private var loadedPath: String? = null
    private var introPulse: ValueAnimator? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        home = findViewById(R.id.home)
        // Hidden entry to the recording tour, for presentations.
        findViewById<View>(R.id.hero).setOnLongClickListener { TourActivity.open(this); true }
        web = findViewById(R.id.web)
        webError = findViewById(R.id.web_error)
        ResidentWeb.setup(this, web, findViewById(R.id.web_progress), webError, webError.findViewById(R.id.retry))

        nav = findViewById(R.id.nav)
        nav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                R.id.tab_home -> showHome()
                R.id.tab_reports -> showWeb("/reports")
                R.id.tab_radar -> showWeb("/radar")
            }
            true
        }
        nav.setOnItemReselectedListener { item -> if (item.itemId != R.id.tab_home) web.scrollTo(0, 0) }

        findViewById<MaterialButton>(R.id.set_default).setOnClickListener { askDefaultBrowser() }
        tile(R.id.action_check, R.drawable.ic_link, R.string.action_check, R.string.action_check_hint, R.color.selected, R.color.ink) {
            focusLinkBox()
        }
        tile(R.id.action_sms, R.drawable.ic_sms, R.string.action_sms, R.string.action_sms_hint, R.color.amber_bg, R.color.amber) {
            openResident("/sms")
        }
        tile(R.id.action_reports, R.drawable.ic_flag, R.string.action_reports, R.string.action_reports_hint, R.color.ok_bg, R.color.ok) {
            nav.selectedItemId = R.id.tab_reports
        }
        tile(R.id.action_radar, R.drawable.ic_radar, R.string.action_radar, R.string.action_radar_hint, R.color.risk_bg, R.color.risk) {
            nav.selectedItemId = R.id.tab_radar
        }
        setting(R.id.setting_dns, R.drawable.ic_globe, R.string.dns_title) { openPrivateDns() }
        setting(R.id.setting_browser, R.drawable.ic_open, R.string.browser_title) { pickBrowser() }
        setting(R.id.setting_language, R.drawable.ic_translate, R.string.language_title) { pickLanguage() }
        setting(R.id.setting_theme, R.drawable.ic_contrast, R.string.theme_title) { pickTheme() }
        setupLinkBox()
        findViewById<View>(R.id.recent_clear).setOnClickListener {
            app.store.clearChecks()
            renderRecent()
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                when {
                    web.visibility == View.VISIBLE && web.canGoBack() -> web.goBack()
                    nav.selectedItemId != R.id.tab_home -> nav.selectedItemId = R.id.tab_home
                    else -> finish()
                }
            }
        })

        if (savedInstanceState == null) playIntro() else findViewById<View>(R.id.intro).visibility = View.GONE
    }

    /** Asked after the entry animation, not over it; used for the "a link you opened turned out to be a scam" alert. */
    private fun askNotifications() {
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != android.content.pm.PackageManager.PERMISSION_GRANTED) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
        }
    }

    override fun onResume() {
        super.onResume()
        refresh()
        WorkManager.getInstance(this).enqueue(OneTimeWorkRequestBuilder<SyncWorker>().build())
    }

    override fun onDestroy() {
        introPulse?.cancel()
        super.onDestroy()
    }

    // --- entry animation ----------------------------------------------------------------------------

    private fun playIntro() {
        val intro = findViewById<View>(R.id.intro)
        val shield = findViewById<View>(R.id.intro_shield)
        val title = findViewById<View>(R.id.intro_title)
        val subtitle = findViewById<View>(R.id.intro_subtitle)
        Motion.popIn(shield, from = 0.4f)
        introPulse = Motion.pulse(findViewById(R.id.intro_ring), periodMs = 1100)
        Motion.stagger(listOf(title, subtitle), startMs = 250, stepMs = 120)
        intro.postDelayed({
            intro.animate().alpha(0f).setDuration(320).withEndAction {
                intro.visibility = View.GONE
                introPulse?.cancel()
                askNotifications()
            }.start()
            revealHome()
        }, 1300)
    }

    private fun revealHome() {
        Motion.stagger(listOf(
            findViewById(R.id.hero), findViewById(R.id.status_card), findViewById(R.id.link_card), findViewById(R.id.stats),
            findViewById(R.id.actions_title), findViewById(R.id.actions_row_1), findViewById(R.id.actions_row_2),
            findViewById(R.id.settings_title), findViewById(R.id.settings_card),
        ), stepMs = 55)
        Motion.popIn(findViewById(R.id.status_icon), delayMs = 260)
    }

    // --- tabs ---------------------------------------------------------------------------------------

    private fun showHome() {
        web.visibility = View.GONE
        webError.visibility = View.GONE
        home.visibility = View.VISIBLE
        home.alpha = 0f
        home.animate().alpha(1f).setDuration(180).start()
        refresh()
    }

    private fun showWeb(path: String) {
        home.visibility = View.GONE
        web.visibility = View.VISIBLE
        web.alpha = 0f
        web.animate().alpha(1f).setDuration(180).start()
        if (loadedPath != path) {
            loadedPath = path
            web.loadUrl(ResidentWeb.url(this, path))
        }
    }

    // --- home content -------------------------------------------------------------------------------

    private fun refresh() {
        val on = Build.VERSION.SDK_INT >= 29 && getSystemService(RoleManager::class.java).isRoleHeld(RoleManager.ROLE_BROWSER)
        findViewById<ImageView>(R.id.status_icon).apply {
            setImageResource(if (on) R.drawable.ic_shield_check else R.drawable.ic_shield_off)
            backgroundTintList = ColorStateList.valueOf(getColor(if (on) R.color.ok_bg else R.color.amber_bg))
            imageTintList = ColorStateList.valueOf(getColor(if (on) R.color.ok else R.color.amber))
        }
        findViewById<TextView>(R.id.status_title).setText(if (on) R.string.status_on_title else R.string.status_off_title)
        findViewById<TextView>(R.id.status_body).setText(if (on) R.string.status_on_body else R.string.status_off_body)
        findViewById<View>(R.id.set_default).visibility = if (on) View.GONE else View.VISIBLE

        findViewById<TextView>(R.id.stat_blocked).text = app.store.blockedCount.toString()
        findViewById<TextView>(R.id.stat_list).text = app.store.listedCount.toString()
        val synced = app.store.syncedAt
        findViewById<TextView>(R.id.stat_list_label).text = getString(R.string.stat_list_label,
            if (synced == 0L) getString(R.string.never) else DateUtils.getRelativeTimeSpanString(synced).toString())

        val browser = Browsers.target(this)
        settingValue(R.id.setting_browser, Browsers.installed(this).firstOrNull { it.first == browser }?.second ?: getString(R.string.none))
        val dnsReady = BuildConfig.DNS_HOST.isNotBlank()
        settingValue(R.id.setting_dns, getString(if (dnsReady) R.string.dns_value else R.string.dns_soon))
        findViewById<View>(R.id.setting_dns).alpha = if (dnsReady) 1f else 0.6f
        settingValue(R.id.setting_language, getString(languageLabel(Appearance.currentLanguage(app.store))))
        settingValue(R.id.setting_theme, getString(themeLabel(app.store.theme)))
        renderRecent()
    }

    // --- recent checks ------------------------------------------------------------------------------

    /** Up to five rows; a tap opens the full result again (the check re-runs, so it is never stale). */
    private fun renderRecent() {
        val checks = app.store.recentChecks().take(5)
        findViewById<View>(R.id.recent_block).visibility = if (checks.isEmpty()) View.GONE else View.VISIBLE
        val list = findViewById<LinearLayout>(R.id.recent_list)
        list.removeAllViews()
        checks.forEachIndexed { i, check ->
            if (i > 0) list.addView(MaterialDivider(this).apply { dividerInsetStart = (66 * resources.displayMetrics.density).toInt() })
            val row = layoutInflater.inflate(R.layout.item_recent, list, false)
            val (icon, tint, bg, label) = when (check.verdict) {
                "block" -> listOf(R.drawable.ic_block, R.color.risk, R.color.risk_bg, R.string.recent_block)
                "warn" -> listOf(R.drawable.ic_warning, R.color.amber, R.color.amber_bg, R.string.recent_warn)
                else -> listOf(R.drawable.ic_check_circle, R.color.ok, R.color.ok_bg, R.string.recent_allow)
            }
            row.findViewById<ImageView>(R.id.recent_icon).apply {
                setImageResource(icon)
                backgroundTintList = ColorStateList.valueOf(getColor(bg))
                imageTintList = ColorStateList.valueOf(getColor(tint))
            }
            val host = Links.host(check.url) ?: check.url
            row.findViewById<TextView>(R.id.recent_host).text = host.replace(".", "[.]")
            val brand = check.brand?.takeIf { check.verdict != "allow" }?.let { " · $it" } ?: ""
            row.findViewById<TextView>(R.id.recent_meta).apply {
                text = getString(label) + brand + " · " + DateUtils.getRelativeTimeSpanString(check.at)
                setTextColor(getColor(if (check.verdict == "allow") R.color.muted else tint))
            }
            row.findViewById<View>(R.id.recent_chevron).scaleX = if (resources.configuration.layoutDirection == View.LAYOUT_DIRECTION_RTL) -1f else 1f
            row.setOnClickListener { openResident(ResidentWeb.checkPath(check.url)) }
            list.addView(row)
        }
    }

    private fun tile(id: Int, icon: Int, title: Int, hint: Int, bg: Int, tint: Int, onClick: () -> Unit) {
        val root = findViewById<View>(id)
        root.findViewById<ImageView>(R.id.action_icon).apply {
            setImageResource(icon)
            backgroundTintList = ColorStateList.valueOf(getColor(bg))
            imageTintList = ColorStateList.valueOf(getColor(tint))
        }
        root.findViewById<TextView>(R.id.action_title).setText(title)
        root.findViewById<TextView>(R.id.action_hint).setText(hint)
        root.setOnClickListener { onClick() }
    }

    private fun setting(id: Int, icon: Int, title: Int, onClick: () -> Unit) {
        val root = findViewById<View>(id)
        root.findViewById<ImageView>(R.id.setting_icon).setImageResource(icon)
        root.findViewById<TextView>(R.id.setting_title).setText(title)
        root.setOnClickListener { onClick() }
    }

    private fun settingValue(id: Int, value: String) {
        findViewById<View>(id).findViewById<TextView>(R.id.setting_value).text = value
    }

    // --- check a link from Home ----------------------------------------------------------------------

    private fun setupLinkBox() {
        val layout = findViewById<TextInputLayout>(R.id.link_layout)
        val input = findViewById<TextInputEditText>(R.id.link_input)
        layout.setEndIconOnClickListener {
            val text = getSystemService(ClipboardManager::class.java).primaryClip
                ?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this)?.toString()?.trim()
            if (text.isNullOrEmpty()) {
                Toast.makeText(this, R.string.link_nothing_to_paste, Toast.LENGTH_SHORT).show()
            } else {
                input.setText(text)
                input.setSelection(input.length())
                layout.error = null
            }
        }
        input.setOnEditorActionListener { _, action, _ ->
            if (action == EditorInfo.IME_ACTION_GO) { checkTyped(); true } else false
        }
        findViewById<MaterialButton>(R.id.link_check).setOnClickListener { checkTyped() }
    }

    /** A bare host ("tamm-pay.com") gets https:// so the X-ray can parse it; text with several links goes to the SMS check. */
    private fun checkTyped() {
        val layout = findViewById<TextInputLayout>(R.id.link_layout)
        val input = findViewById<TextInputEditText>(R.id.link_input)
        val text = input.text?.toString()?.trim().orEmpty()
        if (text.isEmpty()) {
            layout.error = getString(R.string.link_empty)
            return
        }
        layout.error = null
        getSystemService(InputMethodManager::class.java).hideSoftInputFromWindow(input.windowToken, 0)
        val path = if (text.any { it.isWhitespace() }) ResidentWeb.smsPath(text)
            else ResidentWeb.checkPath(if (text.contains("://")) text else "https://$text")
        openResident(path)
        input.text = null
    }

    /** The "Check a link" tile: bring the box on Home into view and open the keyboard. */
    private fun focusLinkBox() {
        val input = findViewById<TextInputEditText>(R.id.link_input)
        (home as NestedScrollView).smoothScrollTo(0, (findViewById<View>(R.id.link_card).top - 24).coerceAtLeast(0))
        input.requestFocus()
        getSystemService(InputMethodManager::class.java).showSoftInput(input, InputMethodManager.SHOW_IMPLICIT)
    }

    /** A check result or the SMS check opens over Home as its own screen, with a back arrow. */
    private fun openResident(path: String) {
        startActivity(Intent(this, ResidentActivity::class.java).putExtra(ResidentActivity.EXTRA_PATH, path))
    }

    // --- language and appearance --------------------------------------------------------------------

    private fun languageLabel(value: String) = when (value) {
        "en" -> R.string.language_en
        "ar" -> R.string.language_ar
        else -> R.string.option_system
    }

    private fun themeLabel(value: String) = when (value) {
        "light" -> R.string.theme_light
        "dark" -> R.string.theme_dark
        else -> R.string.option_system
    }

    /** Changing either recreates the screens; the resident pages pick the new choice up from ?lang= and ?theme=. */
    private fun pickLanguage() {
        val values = Appearance.LANGUAGES
        val current = values.indexOf(Appearance.currentLanguage(app.store)).coerceAtLeast(0)
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.language_title)
            .setSingleChoiceItems(values.map { getString(languageLabel(it)) }.toTypedArray(), current) { dialog, which ->
                dialog.dismiss()
                if (which != current) {
                    app.store.language = values[which]
                    Appearance.setLanguage(values[which])
                }
            }
            .show()
    }

    private fun pickTheme() {
        val values = Appearance.THEMES
        val current = values.indexOf(app.store.theme).coerceAtLeast(0)
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.theme_title)
            .setSingleChoiceItems(values.map { getString(themeLabel(it)) }.toTypedArray(), current) { dialog, which ->
                dialog.dismiss()
                if (which != current) {
                    app.store.theme = values[which]
                    Appearance.setTheme(values[which])
                }
            }
            .show()
    }

    // --- actions ------------------------------------------------------------------------------------

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
            MaterialAlertDialogBuilder(this)
                .setIcon(R.drawable.ic_globe)
                .setTitle(R.string.dns_soon_title)
                .setMessage(R.string.dns_soon_body)
                .setPositiveButton(R.string.turn_on) { _, _ -> askDefaultBrowser() }
                .setNegativeButton(android.R.string.ok, null)
                .show()
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
        MaterialAlertDialogBuilder(this)
            .setTitle(R.string.pick_browser)
            .setItems(all.map { it.second }.toTypedArray()) { _, which ->
                app.store.browser = all[which].first
                refresh()
            }
            .show()
    }
}
