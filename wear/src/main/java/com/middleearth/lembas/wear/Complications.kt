package com.middleearth.lembas.wear

import android.app.PendingIntent
import android.content.ComponentName
import android.content.Intent
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
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
/** The next of Middle-earth's dates: "12d" over "Hobbit Day"; long: "Hobbit Day in 12 days". */
class FeastComplication : LembasComplication() {
    override fun words(now: LocalDateTime): Triple<String, String?, String> {
        val (name, days) = Feasts.next(now.toLocalDate())
        val short = if (days == 0) "today" else "${days}d"
        val long = when (days) { 0 -> "$name today"; 1 -> "$name tomorrow"; else -> "$name in $days days" }
        return Triple(short, name.substringBefore("’").substringBefore(" Day").take(10), long)
    }
}

class NextLookComplication : LembasComplication() {
    override fun words(now: LocalDateTime): Triple<String, String?, String> {
        val (look, at) = WearLooks.next(this, now) ?: return WearLooks.current(this, now).let { Triple(it.title.split(' ')[0], null, it.title) }
        return Triple(clock(at), look.title.split(' ')[0], "${look.title} at ${clock(at)}")
    }
}

/**
 * The look for the Lembas watch face (hidden: the face reads it to know which scene to show).
 * "auto" means follow the sun. Updated the moment the look changes in the app, on the phone or
 * on the PC (through sync).
 */
class LookComplication : ComplicationDataSourceService() {
    override fun onComplicationRequest(request: ComplicationRequest, listener: ComplicationRequestListener) {
        // Durin's Day: the Red Book returns in the evening (following the sun)
        val c = WearLooks.choice(this)
        val look = if (c == WearLook.AUTO && WearLooks.current(this).id == "redbook" && Feasts.durin(java.time.LocalDate.now())) "redbook" else c
        listener.onComplicationData(data(request.complicationType, look))
    }

    override fun getPreviewData(type: ComplicationType): ComplicationData? = data(type, WearLook.AUTO)

    /** The look as text; as a ranged value, the sky's moods from the phone too (bits: 1 rainbow, 2 beacons,
     *  4 smoke, 8 frost, 16 heat, 32 storm), so the face can draw them between the scene and the time. */
    private fun data(type: ComplicationType, look: String): ComplicationData? {
        val text = PlainComplicationText.Builder(look).build()
        val desc = PlainComplicationText.Builder("Lembas look").build()
        val tap = PendingIntent.getActivity(this, 1, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return when (type) {
            // and 1024 under the night watch (from bedtime until five): the lamps go out and the face settles darker
            ComplicationType.RANGED_VALUE -> RangedValueComplicationData.Builder((WearLooks.sky(this) or (if (Touches.nightWatch(this)) 1024 else 0)).toFloat(), 0f, 2047f, desc)
                .setText(text).setTapAction(tap).build()
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(text, desc).setTapAction(tap).build()
            else -> null
        }
    }

    companion object {
        /** Tell the face straight away (after a choice in the app, from the phone, or when a kept look runs out). */
        fun refresh(ctx: android.content.Context) {
            try {
                androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                    .create(ctx, android.content.ComponentName(ctx, LookComplication::class.java)).requestUpdateAll()
            } catch (_: Throwable) { }
        }
    }
}
