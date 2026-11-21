package com.forexbot.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.clickable
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

private val Green = Color(0xFF22C55E)
private val Red = Color(0xFFEF4444)

private fun px(pair: String, v: Double): String =
    String.format(if (pair.endsWith("JPY") || pair.startsWith("XAU")) "%.3f" else "%.5f", v)

private fun sideColor(side: String) = when (side) { "BUY" -> Green; "SELL" -> Red; else -> Color.Gray }

class MainActivity : ComponentActivity() {
    private val vm: MainVM by viewModels()

    private val askNotif = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SignalWorker.ensureChannel(this)
        if (Build.VERSION.SDK_INT >= 33) askNotif.launch(Manifest.permission.POST_NOTIFICATIONS)
        if (Prefs.notify(this) && Prefs.url(this).isNotBlank()) SignalWorker.schedule(this)
        setContent {
            MaterialTheme(colorScheme = if (isSystemInDarkTheme()) darkColorScheme() else lightColorScheme()) {
                App(vm)
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun App(vm: MainVM) {
    var tab by remember { mutableIntStateOf(if (vm.url.isBlank()) 2 else 0) }
    LaunchedEffect(Unit) { if (vm.url.isNotBlank()) vm.refresh() }

    Scaffold(
        topBar = {
            TopAppBar(title = {
                Text("Forex AI Signals")
            })
        },
        bottomBar = {
            NavigationBar {
                listOf("Signals", "Record", "Settings").forEachIndexed { i, label ->
                    NavigationBarItem(
                        selected = tab == i,
                        onClick = { tab = i; vm.select(null) },
                        icon = { Text(listOf("📈", "📋", "⚙️")[i]) },
                        label = { Text(label) },
                    )
                }
            }
        },
    ) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(horizontal = 16.dp)) {
            if (vm.loading) CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally).padding(4.dp))
            vm.error?.let { Text(it, color = Red, modifier = Modifier.padding(vertical = 4.dp)) }
            val sel = vm.selected
            when {
                tab == 0 && sel != null -> Detail(vm, vm.signals.firstOrNull { it.pair == sel })
                tab == 0 -> Signals(vm)
                tab == 1 -> RecordTab(vm)
                else -> SettingsTab(vm)
            }
        }
    }
}

@Composable
fun Signals(vm: MainVM) {
    if (vm.info?.dataSource?.startsWith("synthetic") == true)
        Text("Server is on synthetic DEMO data. Signals are not real.", color = Color(0xFFF59E0B))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
        OutlinedButton(onClick = { vm.refresh() }) { Text("Refresh") }
    }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(vm.signals) { s ->
            Card(Modifier.fillMaxWidth().clickable { vm.select(s.pair) }) {
                Column(Modifier.padding(12.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(s.pair.replace('_', '/'), fontWeight = FontWeight.SemiBold)
                        Text(s.side, color = sideColor(s.side), fontWeight = FontWeight.Bold)
                    }
                    Text("Score ${s.score}  ·  ${s.regime}  ·  ${px(s.pair, s.entry)}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
fun Detail(vm: MainVM, s: Sig?) {
    if (s == null) { LaunchedEffect(Unit) { vm.select(null) }; return }
    var q by remember { mutableStateOf("") }
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        OutlinedButton(onClick = { vm.select(null) }) { Text("← Back") }
        Text(s.pair.replace('_', '/'), style = MaterialTheme.typography.headlineSmall)
        Text(s.side, color = sideColor(s.side), fontWeight = FontWeight.Bold)
        if (s.side != "NONE") {
            Text("Entry ${px(s.pair, s.entry)}\nStop ${px(s.pair, s.stop)}\nTarget ${px(s.pair, s.target)}\nR:R ${s.rr}")
        }
        Text("Why (score ${s.score}):", fontWeight = FontWeight.SemiBold)
        s.reasons.forEach { Text("• $it", style = MaterialTheme.typography.bodySmall) }

        OutlinedTextField(q, { q = it }, label = { Text("Ask the AI (optional)") }, modifier = Modifier.fillMaxWidth())
        Button(onClick = { vm.analyze(s.pair, q) }, enabled = !vm.loading) { Text("AI analysis") }
        vm.aiText?.let { Card(Modifier.fillMaxWidth()) { Text(it, Modifier.padding(12.dp)) } }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { vm.backtest(s.pair, false) }, enabled = !vm.loading) { Text("Backtest") }
            OutlinedButton(onClick = { vm.backtest(s.pair, true) }, enabled = !vm.loading) { Text("+ Walk-forward") }
        }
        vm.btText?.let { Card(Modifier.fillMaxWidth()) { Text(it, Modifier.padding(12.dp)) } }
    }
}

@Composable
fun RecordTab(vm: MainVM) {
    val m = vm.summary
    if (m == null) { Text("No data yet. Set the server in Settings."); return }
    LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Track record", style = MaterialTheme.typography.titleMedium)
                    Text("Signals given: ${m.total}  ·  open: ${m.open}  ·  closed: ${m.closed}")
                    Text("Win rate: ${m.winRate?.let { "$it%" } ?: "–"}  ·  Total: ${m.totalR}R")
                    if (m.closed < 30) Text(
                        "Too few closed signals to judge. Wait for 30+ before trusting these numbers.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Text("Data: ${vm.info?.dataSource}  ·  AI: ${if (vm.info?.aiEnabled == true) "on" else "off"}",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        if (vm.history.isEmpty()) item { Text("No signals yet. They appear here as the bot finds setups.", style = MaterialTheme.typography.bodySmall) }
        items(vm.history) { r ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${r.pair.replace('_', '/')}  ${r.side}", color = sideColor(r.side), fontWeight = FontWeight.SemiBold)
                        Text(r.status.uppercase(), color = when (r.status) { "win" -> Green; "loss" -> Red; else -> Color.Gray })
                    }
                    Text("Entry ${px(r.pair, r.entry)}  SL ${px(r.pair, r.stop)}  TP ${px(r.pair, r.target)}", style = MaterialTheme.typography.bodySmall)
                    if (!r.verdict.isNullOrBlank()) Text("AI: ${r.verdict}  ${r.aiSummary ?: ""}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        item { OutlinedButton(onClick = { vm.refresh() }) { Text("Refresh") } }
    }
}

@Composable
fun SettingsTab(vm: MainVM) {
    Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("Server", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(vm.url, { vm.url = it }, label = { Text("Server URL (https://…)") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(
            vm.token, { vm.token = it }, label = { Text("API token") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("Notify me about new signals", Modifier.weight(1f))
            Switch(vm.notify, { vm.notify = it })
        }
        Button(onClick = { vm.saveSettings() }) { Text("Save & connect") }
        Text(
            "The app only shows signals from your server: your data and AI keys never leave it. You place trades yourself. " +
                "Use HTTPS. Emulator: http://10.0.2.2:8000 works for local testing. " +
                "Not financial advice; trading can lose money.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
