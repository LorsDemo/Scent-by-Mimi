package com.forexbot.app

import android.content.Context

/** App-private storage (sandboxed per app). Holds the server URL and API token. */
object Prefs {
    private fun p(c: Context) = c.getSharedPreferences("bot", Context.MODE_PRIVATE)

    fun url(c: Context): String = p(c).getString("url", "") ?: ""
    fun token(c: Context): String = p(c).getString("token", "") ?: ""
    fun notify(c: Context): Boolean = p(c).getBoolean("notify", true)

    fun save(c: Context, url: String, token: String, notify: Boolean) {
        p(c).edit().putString("url", url.trim()).putString("token", token.trim())
            .putBoolean("notify", notify).apply()
    }

    fun seen(c: Context): Set<String> = p(c).getStringSet("seen", emptySet()) ?: emptySet()
    fun setSeen(c: Context, s: Set<String>) = p(c).edit().putStringSet("seen", s).apply()
}
