package com.middleearth.lembas.wear

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.VibrationEffect
import android.os.Vibrator
import java.time.LocalDateTime
import java.time.ZoneId

/**
 * A gentle tap on the wrist: on the hour, or only at the hobbit mealtimes. Off by default; never
 * between 11pm and 7am. The alarm is inexact (within a minute or so), so it never wakes the watch
 * early or costs battery.
 */
object Chime {
    const val PREF = "chime"          // "off", "hour", "meals"
    private val MEAL_HOURS = setOf(7, 9, 11, 13, 15, 18, 20)   // breakfast, second breakfast, elevenses, luncheon, tea, dinner, supper

    fun mode(ctx: Context) = ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).getString(PREF, "off") ?: "off"
    fun setMode(ctx: Context, m: String) {
        ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).edit().putString(PREF, m).apply()
        schedule(ctx)
    }
    fun label(m: String) = when (m) { "hour" -> "On the hour"; "meals" -> "At mealtimes"; else -> "Off" }
    fun next(m: String) = when (m) { "off" -> "hour"; "hour" -> "meals"; else -> "off" }

    private fun pending(ctx: Context) = PendingIntent.getBroadcast(ctx, 0xc41, Intent(ctx, Tap::class.java),
        PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    fun schedule(ctx: Context) {
        val am = ctx.getSystemService(AlarmManager::class.java) ?: return
        val m = mode(ctx)
        if (m == "off") { am.cancel(pending(ctx)); return }
        var t = LocalDateTime.now().withMinute(0).withSecond(0).withNano(0).plusHours(1)
        while (t.hour >= 23 || t.hour < 7 || (m == "meals" && t.hour !in MEAL_HOURS)) t = t.plusHours(1)
        val at = t.atZone(ZoneId.systemDefault()).toInstant().toEpochMilli()
        am.setWindow(AlarmManager.RTC_WAKEUP, at, 60_000L, pending(ctx))
    }

    class Tap : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            if (intent.action == Intent.ACTION_BOOT_COMPLETED || intent.action == Intent.ACTION_TIME_CHANGED) { schedule(ctx); return }
            try {
                ctx.getSystemService(Vibrator::class.java)?.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 40, 140, 40), -1))
            } catch (_: Throwable) { }
            schedule(ctx)
        }
    }
}
