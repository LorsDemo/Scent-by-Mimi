package com.forexbot.app

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/** Polls the server every ~15 min and notifies about new BUY/SELL signals. */
class SignalWorker(private val ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result {
        if (!Prefs.notify(ctx) || Prefs.url(ctx).isBlank()) return Result.success()
        return try {
            val arr = Api(Prefs.url(ctx), Prefs.token(ctx)).get("/api/record").getJSONArray("signals")
            val seen = Prefs.seen(ctx).toMutableSet()
            for (i in 0 until arr.length()) {
                val s = arr.getJSONObject(i)
                if (s.optString("status") != "open") continue
                if (!seen.add(s.getString("id"))) continue
                val pair = s.getString("pair")
                val dp = if (pair.endsWith("JPY") || pair.startsWith("XAU")) "%.3f" else "%.5f"
                var text = "Entry ${dp.format(s.getDouble("entry"))}  SL ${dp.format(s.getDouble("stop"))}  TP ${dp.format(s.getDouble("target"))}"
                s.optJSONObject("ai")?.let { text += "\nAI: ${it.optString("verdict")}. ${it.optString("summary")}" }
                notify(pair, s.getString("side"), text)
            }
            Prefs.setSeen(ctx, seen.toList().takeLast(200).toSet())
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun notify(pair: String, side: String, text: String) {
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        ensureChannel(ctx)
        val n = NotificationCompat.Builder(ctx, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("$side ${pair.replace('_', '/')}")
            .setContentText(text.lineSequence().first())
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify((pair + side).hashCode(), n)
    }

    companion object {
        const val CHANNEL = "signals"

        fun ensureChannel(ctx: Context) {
            if (Build.VERSION.SDK_INT >= 26) {
                val m = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                m.createNotificationChannel(NotificationChannel(CHANNEL, "Trade signals", NotificationManager.IMPORTANCE_HIGH))
            }
        }

        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<SignalWorker>(15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx)
                .enqueueUniquePeriodicWork("signals", ExistingPeriodicWorkPolicy.UPDATE, req)
        }
    }
}
