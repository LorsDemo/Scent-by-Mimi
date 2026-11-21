package com.forexbot.app

import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Minimal blocking HTTP client for the bot server. Call from a background dispatcher. */
class Api(private val base: String, private val token: String) {

    fun get(path: String): JSONObject = call("GET", path, null)

    fun post(path: String, body: JSONObject? = null): JSONObject = call("POST", path, body)

    private fun call(method: String, path: String, body: JSONObject?): JSONObject {
        if (base.isBlank()) throw IOException("Set the server URL in Settings first")
        val conn = URL(base.trim().trimEnd('/') + path).openConnection() as HttpURLConnection
        try {
            conn.requestMethod = method
            conn.connectTimeout = 15_000
            conn.readTimeout = 120_000
            conn.setRequestProperty("X-API-Key", token)
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                val msg = try { JSONObject(text).optString("detail", text) } catch (e: Exception) { text }
                throw IOException(if (code == 401) "Wrong API token" else msg.ifBlank { "HTTP $code" })
            }
            return JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }
}
