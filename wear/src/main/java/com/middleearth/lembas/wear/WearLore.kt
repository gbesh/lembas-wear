package com.middleearth.lembas.wear

import android.content.Context
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.Year
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import kotlin.math.PI
import kotlin.math.acos
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.tan

/**
 * One of the four looks, as the watch shows them: the same palettes as the watch face, on deep
 * tonal (day) or black (night) backgrounds. Colours are ARGB.
 */
class WearLook(
    val id: String,
    val title: String,
    val background: Int,          // the look's light, for a round screen
    val tileBackground: Long,     // a solid colour for the tile
    val accent: Long,             // the hours, list headings, buttons
    val text: Long,               // minutes, dates, app names
    val lore: Long,               // the Shire date
    val soft: Long,               // the mealtime, secondary text
    val surface: Long,            // app and setting buttons
) {
    companion object {
        const val AUTO = "auto"

        val SHIRE = WearLook("shire", "Shire Morning", R.drawable.wl_shire, 0xFF24452A,
            0xFFFFCF5A, 0xFFF1EDE1, 0xFFB7D08F, 0xFFD9E4C2, 0xFF2F5A34)
        val REDBOOK = WearLook("redbook", "Red Book", R.drawable.wl_redbook, 0xFF6A1D16,
            0xFFF7A23B, 0xFFF1E9DA, 0xFFF2B48A, 0xFFE6C2A8, 0xFF8A2A1A)
        val STARLIT = WearLook("starlit", "Starlit Night", R.drawable.wl_starlit, 0xFF151A40,
            0xFFDAC696, 0xFFECE6D8, 0xFFB9AEE0, 0xFF9C93C8, 0xFF2B2560)
        val ELVEN = WearLook("elven", "Elven Silver", R.drawable.wl_elven, 0xFF0B2A31,
            0xFF7FC8CC, 0xFFE6F4F6, 0xFFB9DADB, 0xFF9FB5BA, 0xFF0F4A52)

        val ALL = listOf(SHIRE, REDBOOK, STARLIT, ELVEN)
        fun byId(id: String) = ALL.firstOrNull { it.id == id } ?: STARLIT
    }
}

object WearLooks {
    private const val PREFS = "lembas"
    const val PREF_LOOK = "look"

    const val PREF_KEEP_UNTIL = "keep_until"

    /** The chosen look, or Follow the sun once a look kept "until the next change" (on the phone) has run out. */
    fun choice(ctx: Context): String {
        val p = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val until = p.getLong(PREF_KEEP_UNTIL, 0)
        if (until > 0 && System.currentTimeMillis() >= until) {
            p.edit().putString(PREF_LOOK, WearLook.AUTO).remove(PREF_KEEP_UNTIL).apply()
            return WearLook.AUTO
        }
        return p.getString(PREF_LOOK, WearLook.AUTO) ?: WearLook.AUTO
    }

    /** Chosen on the watch: kept until changed, and passed to the phone (and from there the PC). */
    fun setChoice(ctx: Context, id: String) {
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(PREF_LOOK, id).remove(PREF_KEEP_UNTIL).apply()
        LookLink.tellPhone(ctx, id)
    }

    /** When the look next changes on its own, and to which (null if one look is kept). */
    fun next(ctx: Context, now: LocalDateTime = LocalDateTime.now()): Pair<WearLook, LocalDateTime>? {
        if (choice(ctx) != WearLook.AUTO) return null
        val here = current(ctx, now)
        var t = now.withSecond(0).withNano(0)
        for (i in 0 until 48 * 4) {   // in quarter-hour steps, then to the minute
            val n = t.plusMinutes(15)
            if (current(ctx, n) != here) {
                var m = t
                while (current(ctx, m) == here) m = m.plusMinutes(1)
                return current(ctx, m) to m
            }
            t = n
        }
        return null
    }

    /** Same schedule as the phone: sunrise→late afternoon Shire, late afternoon→sunset Red Book, 11pm→4am Elven, otherwise Starlit. */
    fun current(ctx: Context, now: LocalDateTime = LocalDateTime.now()): WearLook {
        val c = choice(ctx)
        if (c != WearLook.AUTO) return WearLook.byId(c)
        val day = Sun.today(ZoneId.systemDefault(), now.toLocalDate())
        val m = now.hour * 60 + now.minute
        return when {
            m >= day.sunrise && m < day.evening -> WearLook.SHIRE
            m >= day.evening && m < day.sunset -> WearLook.REDBOOK
            m >= 23 * 60 || m < 4 * 60 -> WearLook.ELVEN
            else -> WearLook.STARLIT
        }
    }
}

/** The Shire calendar, Quenya hours and hobbit mealtimes (as on the phone). */
object Lore {
    fun shireWeekday(d: DayOfWeek): String = when (d) {
        DayOfWeek.SATURDAY -> "Sterday"
        DayOfWeek.SUNDAY -> "Sunday"
        DayOfWeek.MONDAY -> "Monday"
        DayOfWeek.TUESDAY -> "Trewsday"
        DayOfWeek.WEDNESDAY -> "Hevensday"
        DayOfWeek.THURSDAY -> "Mersday"
        DayOfWeek.FRIDAY -> "Highday"
    }

    private val MONTHS = listOf("Afteryule", "Solmath", "Rethe", "Astron", "Thrimidge", "Forelithe",
        "Afterlithe", "Wedmath", "Halimath", "Winterfilth", "Blotmath", "Foreyule")

    fun shireDate(date: LocalDate): String {
        val after = date.monthValue == 12 && date.dayOfMonth >= 21
        val start = LocalDate.of(if (after) date.year else date.year - 1, 12, 21)
        var d = ChronoUnit.DAYS.between(start, date).toInt()
        val leap = Year.isLeap((if (after) date.year else date.year - 1) + 1L)
        if (d == 0) return "1 Yule"
        if (d == 1) return "2 Yule"
        d -= 2
        if (d < 180) return "${d % 30 + 1} ${MONTHS[d / 30]}"
        d -= 180
        val lithe = if (leap) listOf("1 Lithe", "Mid-year’s Day", "Overlithe", "2 Lithe") else listOf("1 Lithe", "Mid-year’s Day", "2 Lithe")
        if (d < lithe.size) return lithe[d]
        d -= lithe.size
        if (d < 180) return "${d % 30 + 1} ${MONTHS[6 + d / 30]}"
        return "1 Yule"
    }

    fun quenya(hour: Int): String = when (hour) {
        in 4..6 -> "Tindómë"
        in 7..17 -> "Aurë"
        in 18..20 -> "Undómë"
        else -> "Lómë"
    }

    fun meal(hour: Int): String = when (hour) {
        5, 6 -> "Kettle on"
        7, 8 -> "Breakfast"
        9, 10 -> "Second breakfast"
        11 -> "Elevenses"
        12, 13 -> "Luncheon"
        14 -> "A stroll in the garden"
        15, 16 -> "Afternoon tea"
        17 -> "A pint at the Green Dragon"
        18, 19 -> "Dinner"
        20, 21 -> "Supper"
        else -> "The Shire sleeps"
    }
}

/** Sunrise, solar noon and sunset from the time zone's main city (no location needed). */
object Sun {
    /** Minutes after midnight; [evening] is when the afternoon sun is down to 15° (the fireside look). */
    class Day(val sunrise: Int, val noon: Int, val evening: Int, val sunset: Int)

    // The same table as the phone (lembas-android Sun.kt) and the watch face, so all three switch together.
    private val CITIES: Map<String, Pair<Double, Double>> = mapOf(
        "Australia/Sydney" to (-33.87 to 151.21), "Australia/Melbourne" to (-37.81 to 144.96),
        "Australia/Brisbane" to (-27.47 to 153.03), "Australia/Adelaide" to (-34.93 to 138.60),
        "Australia/Perth" to (-31.95 to 115.86), "Australia/Hobart" to (-42.88 to 147.33),
        "Australia/Darwin" to (-12.46 to 130.84), "Australia/Canberra" to (-35.28 to 149.13),
        "Australia/Lord_Howe" to (-31.55 to 159.08), "Australia/Broken_Hill" to (-31.95 to 141.45),
        "Pacific/Auckland" to (-36.85 to 174.76), "Pacific/Fiji" to (-18.14 to 178.44),
        "Asia/Tokyo" to (35.68 to 139.69), "Asia/Seoul" to (37.57 to 126.98),
        "Asia/Shanghai" to (31.23 to 121.47), "Asia/Hong_Kong" to (22.32 to 114.17),
        "Asia/Singapore" to (1.35 to 103.82), "Asia/Kolkata" to (19.08 to 72.88),
        "Asia/Dubai" to (25.20 to 55.27), "Asia/Jakarta" to (-6.21 to 106.85),
        "Asia/Manila" to (14.60 to 120.98), "Asia/Bangkok" to (13.76 to 100.50),
        "Europe/London" to (51.51 to -0.13), "Europe/Dublin" to (53.35 to -6.26),
        "Europe/Paris" to (48.86 to 2.35), "Europe/Berlin" to (52.52 to 13.40),
        "Europe/Madrid" to (40.42 to -3.70), "Europe/Rome" to (41.90 to 12.50),
        "Europe/Amsterdam" to (52.37 to 4.90), "Europe/Stockholm" to (59.33 to 18.07),
        "Europe/Athens" to (37.98 to 23.73), "Europe/Moscow" to (55.76 to 37.62),
        "Africa/Johannesburg" to (-26.20 to 28.05), "Africa/Cairo" to (30.04 to 31.24),
        "Africa/Lagos" to (6.52 to 3.38), "Africa/Nairobi" to (-1.29 to 36.82),
        "America/New_York" to (40.71 to -74.01), "America/Chicago" to (41.88 to -87.63),
        "America/Denver" to (39.74 to -104.99), "America/Los_Angeles" to (34.05 to -118.24),
        "America/Phoenix" to (33.45 to -112.07), "America/Toronto" to (43.65 to -79.38),
        "America/Vancouver" to (49.28 to -123.12), "America/Mexico_City" to (19.43 to -99.13),
        "America/Sao_Paulo" to (-23.55 to -46.63), "America/Argentina/Buenos_Aires" to (-34.60 to -58.38),
        "America/Santiago" to (-33.45 to -70.67), "America/Bogota" to (4.71 to -74.07),
        "America/Lima" to (-12.05 to -77.04), "Pacific/Honolulu" to (21.31 to -157.86),
        "America/Anchorage" to (61.22 to -149.90),
    )

    fun today(zone: ZoneId, date: LocalDate): Day {
        val offsetMin = zone.rules.getOffset(date.atStartOfDay(zone).plusHours(12).toInstant()).totalSeconds / 60.0
        val (lat, lon) = CITIES[zone.id] ?: (0.0 to offsetMin / 4.0)
        val g = 2 * PI / 365.0 * (date.dayOfYear - 1)
        val eot = 229.18 * (0.000075 + 0.001868 * cos(g) - 0.032077 * sin(g) - 0.014615 * cos(2 * g) - 0.040849 * sin(2 * g))
        val dec = 0.006918 - 0.399912 * cos(g) + 0.070257 * sin(g) - 0.006758 * cos(2 * g) +
            0.000907 * sin(2 * g) - 0.002697 * cos(3 * g) + 0.00148 * sin(3 * g)
        val noon = 720 - 4 * lon - eot + offsetMin
        val latR = Math.toRadians(lat)
        val cosHa = cos(Math.toRadians(90.833)) / (cos(latR) * cos(dec)) - tan(latR) * tan(dec)
        val ha = when {
            cosHa >= 1 -> 0.0
            cosHa <= -1 -> 180.0
            else -> Math.toDegrees(acos(cosHa))
        }
        val cosHe = (sin(Math.toRadians(15.0)) - sin(latR) * sin(dec)) / (cos(latR) * cos(dec))
        val he = when {
            cosHe >= 1 -> 0.0
            cosHe <= -1 -> 180.0
            else -> Math.toDegrees(acos(cosHe))
        }.coerceAtMost(ha)
        return Day((noon - 4 * ha).toInt().coerceIn(0, 1439), noon.toInt().coerceIn(0, 1439),
            (noon + 4 * he).toInt().coerceIn(0, 1439), (noon + 4 * ha).toInt().coerceIn(0, 1439))
    }
}
