package ae.kartoshka.gatekeeper

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat

/**
 * Language and theme chosen inside the app (Settings on Home). "system" follows the phone and is the default.
 * The resident pages in the WebView get the resolved choice as ?lang= and ?theme=, so they match the native screens.
 */
object Appearance {
    val LANGUAGES = listOf("system", "en", "ar")
    val THEMES = listOf("system", "light", "dark")

    /** Called once from GatekeeperApp. Android 13+ keeps the per-app language itself; older versions need it re-applied. */
    fun applyAtStart(store: Store) {
        setTheme(store.theme)
        if (Build.VERSION.SDK_INT < 33 && store.language != "system") setLanguage(store.language)
    }

    fun setTheme(value: String) = AppCompatDelegate.setDefaultNightMode(
        when (value) {
            "light" -> AppCompatDelegate.MODE_NIGHT_NO
            "dark" -> AppCompatDelegate.MODE_NIGHT_YES
            else -> AppCompatDelegate.MODE_NIGHT_FOLLOW_SYSTEM
        }
    )

    fun setLanguage(value: String) = AppCompatDelegate.setApplicationLocales(
        if (value == "system") LocaleListCompat.getEmptyLocaleList() else LocaleListCompat.forLanguageTags(value)
    )

    /** The in-app language as the user last chose it (also when chosen in Android 13's per-app language settings). */
    fun currentLanguage(store: Store): String {
        val tags = AppCompatDelegate.getApplicationLocales()
        if (tags.isEmpty) return if (Build.VERSION.SDK_INT >= 33) "system" else store.language
        return if (tags[0]?.language == "ar") "ar" else "en"
    }

    fun webLanguage(context: Context): String =
        if (context.resources.configuration.locales[0].language == "ar") "ar" else "en"

    fun webTheme(context: Context): String =
        if (context.resources.configuration.uiMode and Configuration.UI_MODE_NIGHT_MASK == Configuration.UI_MODE_NIGHT_YES) "dark" else "light"
}
