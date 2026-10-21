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

        val SHIRE = WearLook("shire", "Shire Morning", R.drawable.wl_shire, 0xFF0E1910,
            0xFFF2D06B, 0xFFF1F4E6, 0xFFB9D79A, 0xFFA3B59B, 0xFF1C2B1E)
        val REDBOOK = WearLook("redbook", "Red Book", R.drawable.wl_redbook, 0xFF1A0B09,
            0xFFF07A62, 0xFFF6ECD6, 0xFFE6C79A, 0xFFC2A08A, 0xFF2E1814)
        val STARLIT = WearLook("starlit", "Starlit Night", R.drawable.wl_starlit, 0xFF000000,
            0xFFE9CC88, 0xFFF6F0E2, 0xFFA9BCE6, 0xFF8E97B0, 0xFF171B29)
        val ELVEN = WearLook("elven", "Elven Silver", R.drawable.wl_elven, 0xFF000000,
            0xFFC6DDE8, 0xFFF4F7F8, 0xFFA2B3BB, 0xFF7F8C93, 0xFF161B1E)

        val ALL = listOf(SHIRE, REDBOOK, STARLIT, ELVEN)
        fun byId(id: String) = ALL.firstOrNull { it.id == id } ?: STARLIT
    }
}

object WearLooks {
    private const val PREFS = "lembas"
    const val PREF_LOOK = "look"

    fun choice(ctx: Context): String =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(PREF_LOOK, WearLook.AUTO) ?: WearLook.AUTO

    fun setChoice(ctx: Context, id: String) =
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(PREF_LOOK, id).apply()

    /** Same schedule as the phone: sunrise→midday Shire, midday→sunset Red Book, 11pm→4am Elven, otherwise Starlit. */
    fun current(ctx: Context, now: LocalDateTime = LocalDateTime.now()): WearLook {
        val c = choice(ctx)
        if (c != WearLook.AUTO) return WearLook.byId(c)
        val day = Sun.today(ZoneId.systemDefault(), now.toLocalDate())
        val m = now.hour * 60 + now.minute
        return when {
            m >= day.sunrise && m < day.noon -> WearLook.SHIRE
            m >= day.noon && m < day.sunset -> WearLook.REDBOOK
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
    class Day(val sunrise: Int, val noon: Int, val sunset: Int)

    private val CITIES: Map<String, Pair<Double, Double>> = mapOf(
        "Australia/Sydney" to (-33.87 to 151.21), "Australia/Melbourne" to (-37.81 to 144.96),
        "Australia/Brisbane" to (-27.47 to 153.03), "Australia/Adelaide" to (-34.93 to 138.60),
        "Australia/Perth" to (-31.95 to 115.86), "Australia/Hobart" to (-42.88 to 147.33),
        "Australia/Darwin" to (-12.46 to 130.84), "Pacific/Auckland" to (-36.85 to 174.76),
        "Asia/Tokyo" to (35.68 to 139.69), "Asia/Seoul" to (37.57 to 126.98), "Asia/Shanghai" to (31.23 to 121.47),
        "Asia/Singapore" to (1.35 to 103.82), "Asia/Kolkata" to (19.08 to 72.88), "Asia/Dubai" to (25.20 to 55.27),
        "Europe/London" to (51.51 to -0.13), "Europe/Paris" to (48.86 to 2.35), "Europe/Berlin" to (52.52 to 13.40),
        "Europe/Madrid" to (40.42 to -3.70), "Europe/Rome" to (41.90 to 12.50), "Europe/Moscow" to (55.76 to 37.62),
        "Africa/Johannesburg" to (-26.20 to 28.05), "America/New_York" to (40.71 to -74.01),
        "America/Chicago" to (41.88 to -87.63), "America/Denver" to (39.74 to -104.99),
        "America/Los_Angeles" to (34.05 to -118.24), "America/Toronto" to (43.65 to -79.38),
        "America/Sao_Paulo" to (-23.55 to -46.63), "Pacific/Honolulu" to (21.31 to -157.86),
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
        return Day((noon - 4 * ha).toInt().coerceIn(0, 1439), noon.toInt().coerceIn(0, 1439), (noon + 4 * ha).toInt().coerceIn(0, 1439))
    }
}
