package com.forexbot.app

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

data class Sig(
    val pair: String, val side: String, val score: Double, val regime: String,
    val entry: Double, val stop: Double, val target: Double, val rr: Double,
    val reasons: List<String>,
)

data class Rec(
    val pair: String, val side: String, val entry: Double, val stop: Double, val target: Double,
    val status: String, val verdict: String?, val aiSummary: String?,
)

data class Summary(val total: Int, val open: Int, val closed: Int, val winRate: Double?, val totalR: Double)

data class Info(val dataSource: String, val aiEnabled: Boolean)

private fun JSONArray?.strings(): List<String> = if (this == null) emptyList() else (0 until length()).map { getString(it) }

fun JSONObject.toSig() = Sig(
    getString("pair"), getString("side"), getDouble("score"), optString("regime"),
    getDouble("entry"), getDouble("stop"), getDouble("target"), optDouble("rr", 0.0),
    optJSONArray("reasons").strings(),
)

private fun JSONObject.toRec(): Rec {
    val ai = optJSONObject("ai")
    return Rec(
        getString("pair"), getString("side"), getDouble("entry"), getDouble("stop"), getDouble("target"),
        optString("status"), ai?.optString("verdict"), ai?.optString("summary"),
    )
}

class MainVM(app: Application) : AndroidViewModel(app) {
    var url by mutableStateOf(Prefs.url(app))
    var token by mutableStateOf(Prefs.token(app))
    var notify by mutableStateOf(Prefs.notify(app))

    var signals by mutableStateOf(listOf<Sig>())
    var info by mutableStateOf<Info?>(null)
    var summary by mutableStateOf<Summary?>(null)
    var history by mutableStateOf(listOf<Rec>())
    var selected by mutableStateOf<String?>(null)
    var aiText by mutableStateOf<String?>(null)
    var btText by mutableStateOf<String?>(null)
    var error by mutableStateOf<String?>(null)
    var loading by mutableStateOf(false)

    private fun api() = Api(url, token)

    private fun <T> launchIo(block: () -> T, ok: (T) -> Unit) {
        viewModelScope.launch {
            loading = true
            error = null
            try {
                ok(withContext(Dispatchers.IO) { block() })
            } catch (e: Exception) {
                error = e.message ?: e.toString()
            } finally {
                loading = false
            }
        }
    }

    fun refresh() = launchIo({
        val a = api()
        Triple(a.get("/api/status"), a.get("/api/signals"), a.get("/api/record"))
    }) { (st, g, r) ->
        info = Info(st.getString("data_source"), st.getBoolean("ai_enabled"))
        val arr = g.getJSONArray("signals")
        signals = (0 until arr.length()).map { arr.getJSONObject(it).toSig() }
        val m = r.getJSONObject("summary")
        summary = Summary(
            m.getInt("total"), m.getInt("open"), m.getInt("closed"),
            if (m.isNull("win_rate")) null else m.getDouble("win_rate"), m.getDouble("total_R"),
        )
        val h = r.getJSONArray("signals")
        history = (0 until h.length()).map { h.getJSONObject(it).toRec() }
    }

    fun select(pair: String?) {
        selected = pair
        aiText = null
        btText = null
    }

    fun analyze(pair: String, question: String) = launchIo({
        api().post("/api/analyze", JSONObject().put("pair", pair).apply { if (question.isNotBlank()) put("question", question) })
    }) { d ->
        val a = d.getJSONObject("ai")
        aiText = "${a.optString("verdict")} (confidence ${a.optInt("confidence")}%)\n\n" +
            "${a.optString("summary")}\n\nKey risk: ${a.optString("key_risk")}\n" +
            "Invalidation: ${a.optString("invalidation")}"
    }

    fun backtest(pair: String, walk: Boolean) = launchIo({
        api().get("/api/backtest/$pair" + if (walk) "?walk=true" else "")
    }) { d ->
        val r = d.getJSONObject("result")
        val sb = StringBuilder()
        if (r.optInt("trades") == 0) {
            sb.append("No trades generated.")
        } else {
            sb.append("Trades ${r.getInt("trades")}  |  Win rate ${r.getDouble("win_rate")}%\n")
            sb.append("Profit factor ${r.get("profit_factor")}  |  Expectancy ${r.getDouble("expectancy_R")}R\n")
            sb.append("Return ${r.getDouble("net_return_pct")}%  |  Max drawdown ${r.getDouble("max_drawdown_pct")}%")
        }
        d.optJSONArray("walk_forward")?.let { w ->
            val folds = (0 until w.length()).joinToString(" | ") { w.getJSONObject(it).opt("net_return_pct")?.toString() ?: "n/a" }
            sb.append("\n\nWalk-forward folds (return %): $folds\nAn edge present in only one fold is probably luck.")
        }
        if (d.optString("data_source").startsWith("synthetic")) sb.append("\n\nSYNTHETIC DEMO DATA: results are meaningless.")
        btText = sb.toString()
    }

    fun saveSettings() {
        val app = getApplication<Application>()
        Prefs.save(app, url, token, notify)
        if (notify) SignalWorker.schedule(app)
        refresh()
    }
}
