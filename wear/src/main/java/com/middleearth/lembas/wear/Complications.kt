package com.middleearth.lembas.wear

import android.app.PendingIntent
import android.content.ComponentName
import android.content.Intent
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * Lembas on any watch face: the Shire date, the hobbit mealtime and when the look next changes,
 * as complications you can add to other faces (long-press the face > Edit > a complication > Lembas).
 */
abstract class LembasComplication : ComplicationDataSourceService() {
    /** (short text, title for short slots, long text) for this moment. */
    abstract fun words(now: LocalDateTime): Triple<String, String?, String>

    private fun data(type: ComplicationType, now: LocalDateTime): ComplicationData? {
        val (short, title, long) = words(now)
        val tap = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val desc = PlainComplicationText.Builder(long).build()
        return when (type) {
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(PlainComplicationText.Builder(short).build(), desc)
                .apply { if (title != null) setTitle(PlainComplicationText.Builder(title).build()) }
                .setTapAction(tap).build()
            ComplicationType.LONG_TEXT -> LongTextComplicationData.Builder(PlainComplicationText.Builder(long).build(), desc)
                .setTapAction(tap).build()
            else -> null
        }
    }

    override fun onComplicationRequest(request: ComplicationRequest, listener: ComplicationRequestListener) {
        listener.onComplicationData(data(request.complicationType, LocalDateTime.now()))
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? = data(type, LocalDateTime.of(2026, 10, 31, 10, 30))

    protected fun clock(t: LocalDateTime): String =
        t.format(DateTimeFormatter.ofPattern(if (android.text.format.DateFormat.is24HourFormat(this)) "H:mm" else "h:mm"))
}

/** "10 Blotmath" (short: "10", titled "Blotmath"). */
class ShireDateComplication : LembasComplication() {
    override fun words(now: LocalDateTime): Triple<String, String?, String> {
        val full = Lore.shireDate(now.toLocalDate())
        val parts = full.split(' ', limit = 2)
        return if (parts.size == 2 && parts[0].all { it.isDigit() }) Triple(parts[0], parts[1].take(9), "${Lore.shireWeekday(now.dayOfWeek)} · $full")
        else Triple(full.take(7), null, "${Lore.shireWeekday(now.dayOfWeek)} · $full")
    }
}

/** "Elevenses", "Afternoon tea"… */
class MealComplication : LembasComplication() {
    override fun words(now: LocalDateTime): Triple<String, String?, String> {
        val meal = Lore.meal(now.hour)
        return Triple(meal.split(' ').firstOrNull { it.length > 3 }?.take(7) ?: meal.take(7), null, meal)
    }
}

/** "Starlit 7:21" (long: "Starlit Night at 7:21 pm"). */
class NextLookComplication : LembasComplication() {
    override fun words(now: LocalDateTime): Triple<String, String?, String> {
        val (look, at) = WearLooks.next(this, now) ?: return WearLooks.current(this, now).let { Triple(it.title.split(' ')[0], null, it.title) }
        return Triple(clock(at), look.title.split(' ')[0], "${look.title} at ${clock(at)}")
    }
}
