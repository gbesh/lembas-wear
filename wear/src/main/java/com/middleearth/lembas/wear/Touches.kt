package com.middleearth.lembas.wear

import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RadialGradient
import android.graphics.Shader
import android.graphics.Typeface
import android.os.Bundle
import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.concurrent.futures.CallbackToFutureAdapter
import androidx.wear.protolayout.ActionBuilders
import androidx.wear.protolayout.ColorBuilders.argb
import androidx.wear.protolayout.DimensionBuilders.dp
import androidx.wear.protolayout.DimensionBuilders.expand
import androidx.wear.protolayout.DimensionBuilders.sp
import androidx.wear.protolayout.LayoutElementBuilders
import androidx.wear.protolayout.ModifiersBuilders
import androidx.wear.protolayout.ResourceBuilders
import androidx.wear.protolayout.TimelineBuilders
import androidx.wear.tiles.RequestBuilders
import androidx.wear.tiles.TileBuilders
import androidx.wear.tiles.TileService
import androidx.wear.watchface.complications.data.ComplicationData
import androidx.wear.watchface.complications.data.ComplicationType
import androidx.wear.watchface.complications.data.LongTextComplicationData
import androidx.wear.watchface.complications.data.PlainComplicationText
import androidx.wear.watchface.complications.data.RangedValueComplicationData
import androidx.wear.watchface.complications.data.ShortTextComplicationData
import androidx.wear.watchface.complications.datasource.ComplicationDataSourceService
import androidx.wear.watchface.complications.datasource.ComplicationRequest
import com.google.android.gms.wearable.Wearable
import com.google.common.util.concurrent.ListenableFuture
import java.time.LocalTime
import kotlin.math.sin

/**
 * The phone's small touches on the watch: the walk to Mount Doom and the hobbit forecast as
 * complications, the night watch for the face, a Sindarin greeting, and three tiles: the Horn of
 * Gondor (find your phone), the Phial of Galadriel (a soft starlight torch), and the smoke-ring
 * focus timer (kept in step with the phone).
 */
object Touches {
    private const val PREFS = "lembas"
    const val PREF_WALK_KM = "walk_km"
    const val PREF_WALK_NEXT = "walk_next"
    const val PREF_WALK_NEXT_KM = "walk_next_km"
    const val PREF_WALK_AT = "walk_at"
    const val PREF_BEDTIME = "bedtime"
    const val PREF_FOCUS_END = "focus_end"
    const val ROAD_KM = 2863f

    private fun prefs(ctx: Context) = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    /** Under the night watch: from bedtime (set on the phone) until five in the morning. */
    fun nightWatch(ctx: Context, t: LocalTime = LocalTime.now()): Boolean {
        val bed = prefs(ctx).getInt(PREF_BEDTIME, 23 * 60)
        if (bed < 0) return false
        val m = t.hour * 60 + t.minute
        return (m - bed + 1440) % 1440 < (5 * 60 - bed + 1440) % 1440
    }

    /** A Sindarin greeting for the hour, and its English (the same as the phone's). */
    fun greeting(t: LocalTime = LocalTime.now()): Pair<String, String> = when (t.hour) {
        in 4..6 -> "Le suilon" to "I greet you"
        in 7..10 -> "Aur vaer" to "good morning"
        in 11..13 -> "Suilad" to "greetings"
        in 14..17 -> "Galu" to "good fortune"
        in 18..20 -> "Mae govannen" to "well met"
        in 21..23 -> "Losto mae" to "sleep well"
        else -> "Novaer" to "be well"
    }

    fun walkKm(ctx: Context) = prefs(ctx).getFloat(PREF_WALK_KM, -1f)
    fun walkNext(ctx: Context) = prefs(ctx).getString(PREF_WALK_NEXT, "") ?: ""
    fun walkNextKm(ctx: Context) = prefs(ctx).getInt(PREF_WALK_NEXT_KM, 0)
    fun focusEnd(ctx: Context) = prefs(ctx).getLong(PREF_FOCUS_END, 0L).takeIf { it > System.currentTimeMillis() } ?: 0L

    /** Send a message to the phone (the horn, focus). [done] gets false if no phone was reachable. */
    fun tellPhone(ctx: Context, path: String, data: String = "", done: (Boolean) -> Unit = {}) {
        try {
            Wearable.getNodeClient(ctx).connectedNodes.addOnSuccessListener { nodes ->
                if (nodes.isEmpty()) { done(false); return@addOnSuccessListener }
                for (n in nodes) Wearable.getMessageClient(ctx).sendMessage(n.id, path, data.toByteArray())
                done(true)
            }.addOnFailureListener { done(false) }
        } catch (_: Throwable) { done(false) }
    }

    fun refreshAll(ctx: Context) {
        for (c in listOf(JourneyComplication::class.java, ForecastComplication::class.java)) try {
            androidx.wear.watchface.complications.datasource.ComplicationDataSourceUpdateRequester
                .create(ctx, android.content.ComponentName(ctx, c)).requestUpdateAll()
        } catch (_: Throwable) { }
        try { TileService.getUpdater(ctx).requestUpdate(FocusTile::class.java) } catch (_: Throwable) { }
    }
}

// ------------------------------------------------------------------ complications

/** The walk to Mount Doom: how far along the road (as a ranged value), and the next place. */
class JourneyComplication : ComplicationDataSourceService() {
    override fun onComplicationRequest(request: ComplicationRequest, listener: ComplicationRequestListener) {
        listener.onComplicationData(data(request.complicationType, Touches.walkKm(this), Touches.walkNext(this), Touches.walkNextKm(this)))
    }
    override fun getPreviewData(type: ComplicationType): ComplicationData? = data(type, 312f, "Weathertop", 71)

    private fun data(type: ComplicationType, km: Float, next: String, left: Int): ComplicationData? {
        val tap = PendingIntent.getActivity(this, 2, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val walking = km >= 0f
        val long = when { !walking -> "Start the walk in Lembas on your phone"; next.isEmpty() -> "Mount Doom: the whole road"; else -> "${km.toInt()} km · ${next.replaceFirstChar { it.uppercase() }} in $left km" }
        val desc = PlainComplicationText.Builder(long).build()
        val short = if (!walking) "–" else if (next.isEmpty()) "Doom" else "${left}km"
        val title = if (!walking) "Walk" else next.removePrefix("the ").split(' ').first().take(9)
        return when (type) {
            ComplicationType.RANGED_VALUE -> RangedValueComplicationData.Builder(km.coerceAtLeast(0f), 0f, Touches.ROAD_KM, desc)
                .setText(PlainComplicationText.Builder(short).build()).setTitle(PlainComplicationText.Builder(title).build()).setTapAction(tap).build()
            ComplicationType.SHORT_TEXT -> ShortTextComplicationData.Builder(PlainComplicationText.Builder(short).build(), desc)
                .setTitle(PlainComplicationText.Builder(title).build()).setTapAction(tap).build()
            ComplicationType.LONG_TEXT -> LongTextComplicationData.Builder(PlainComplicationText.Builder(long).build(), desc).setTapAction(tap).build()
            else -> null
        }
    }
}

/** Today's weather as a hobbit would put it ("Rain by elevenses, clear for supper"), from the phone. */
class ForecastComplication : ComplicationDataSourceService() {
    override fun onComplicationRequest(request: ComplicationRequest, listener: ComplicationRequestListener) {
        listener.onComplicationData(data(request.complicationType, WearLooks.forecast(this)))
    }
    override fun getPreviewData(type: ComplicationType): ComplicationData? = data(type, "Rain by elevenses, clear for supper")

    private fun data(type: ComplicationType, f: String): ComplicationData? {
        val text = f.ifEmpty { "No word of the weather" }
        val desc = PlainComplicationText.Builder(text).build()
        val tap = PendingIntent.getActivity(this, 3, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return when (type) {
            ComplicationType.LONG_TEXT -> LongTextComplicationData.Builder(PlainComplicationText.Builder(text).build(), desc).setTapAction(tap).build()
            ComplicationType.SHORT_TEXT -> {
                val word = Regex("(?i)rain|storm|snow|fog|frost|hot|cold|clear|fine|cloud|wind|sun").find(f)?.value?.replaceFirstChar { it.uppercase() } ?: "Fair"
                ShortTextComplicationData.Builder(PlainComplicationText.Builder(word).build(), desc).setTapAction(tap).build()
            }
            else -> null
        }
    }
}

// ------------------------------------------------------------------ the Horn of Gondor

/** Sounds the horn on your phone (even on silent), and its torch flashes, so you can find it. */
class HornActivity : Activity() {
    private lateinit var line: TextView
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val box = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER
            setBackgroundColor(0xFF14100C.toInt())
        }
        box.addView(TextView(this).apply { text = "📯"; textSize = 40f; gravity = Gravity.CENTER })
        line = TextView(this).apply { text = "Sounding the horn…"; textSize = 15f; setTextColor(0xFFF2E6C8.toInt()); gravity = Gravity.CENTER; setPadding(24, 12, 24, 4) }
        box.addView(line)
        box.addView(TextView(this).apply {
            text = "Tap to sound it again"; textSize = 12f; setTextColor(0x99F2E6C8.toInt()); gravity = Gravity.CENTER
        })
        box.setOnClickListener { blow() }
        setContentView(box)
        blow()
    }
    private fun blow() {
        line.text = "Sounding the horn…"
        try { getSystemService(Vibrator::class.java)?.vibrate(VibrationEffect.createWaveform(longArrayOf(0, 300, 120, 500), -1)) } catch (_: Throwable) { }
        Touches.tellPhone(this, "/lembas/horn") { ok ->
            runOnUiThread { line.text = if (ok) "Your phone is sounding\nthe Horn of Gondor" else "Your phone isn't in reach" }
        }
    }
}

// ------------------------------------------------------------------ the Phial of Galadriel

/** A torch: the screen fills with soft starlight at full brightness. Tap to put it away. */
class PhialActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.attributes = window.attributes.apply { screenBrightness = 1f }
        setContentView(object : View(this) {
            private val start = SystemClock.uptimeMillis()
            private val p = Paint(Paint.ANTI_ALIAS_FLAG)
            init { contentDescription = "The Phial of Galadriel: a starlight torch. Tap to close." }
            override fun onDraw(c: Canvas) {
                val t = (SystemClock.uptimeMillis() - start) / 1000f
                val w = width.toFloat(); val h = height.toFloat()
                val r = maxOf(w, h) * (.75f + .03f * sin(t * 1.4f))
                p.shader = RadialGradient(w / 2, h / 2, r, intArrayOf(0xFFFFFFFF.toInt(), 0xFFF2F6FF.toInt(), 0xFFDDE7FF.toInt()), floatArrayOf(0f, .55f, 1f), Shader.TileMode.CLAMP)
                c.drawRect(0f, 0f, w, h, p)
                p.shader = null
                for (k in 0 until 10) {   // a few motes of light turning slowly
                    val a = t * .3f + k * .628f
                    p.color = 0xFFB9CCFF.toInt(); p.alpha = (60 + 50 * sin(t * 2 + k)).toInt()
                    c.drawCircle(w / 2 + kotlin.math.cos(a) * w * .32f, h / 2 + sin(a) * h * .32f, 3f, p)
                }
                postInvalidateOnAnimation()
            }
            override fun onTouchEvent(e: MotionEvent): Boolean { if (e.actionMasked == MotionEvent.ACTION_UP) finish(); return true }
        })
    }
}

// ------------------------------------------------------------------ smoke-ring focus

/** Start or stop a smoke-ring focus (it runs on the phone, so the scene and the ring are there too). */
class FocusActivity : Activity() {
    private lateinit var state: TextView
    private lateinit var button: TextView
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val box = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; gravity = Gravity.CENTER; setBackgroundColor(0xFF101418.toInt()) }
        state = TextView(this).apply { textSize = 15f; setTextColor(0xFFECE6D8.toInt()); gravity = Gravity.CENTER; setPadding(24, 0, 24, 12) }
        button = TextView(this).apply {
            textSize = 15f; setTextColor(0xFF101418.toInt()); gravity = Gravity.CENTER; setPadding(36, 18, 36, 18)
            background = android.graphics.drawable.GradientDrawable().apply { cornerRadius = 999f; setColor(0xFFDAC696.toInt()) }
        }
        box.addView(state); box.addView(button)
        setContentView(box)
        show()
        button.setOnClickListener {
            val running = Touches.focusEnd(this) > 0
            Touches.tellPhone(this, "/lembas/focus", if (running) "stop" else "start:25") { ok ->
                runOnUiThread {
                    if (!ok) { state.text = "Your phone isn't in reach"; return@runOnUiThread }
                    getSharedPreferences("lembas", MODE_PRIVATE).edit().putLong(Touches.PREF_FOCUS_END, if (running) 0L else System.currentTimeMillis() + 25 * 60_000L).apply()
                    Touches.refreshAll(this)
                    show()
                    if (!running) finish()
                }
            }
        }
    }
    private fun show() {
        val end = Touches.focusEnd(this)
        if (end > 0) { state.text = "Focusing · ${((end - System.currentTimeMillis()) / 60_000 + 1)} min to go"; button.text = "Stop" }
        else { state.text = "A quiet stretch of focus,\nand a smoke ring at the end"; button.text = "Focus 25 min" }
    }
}

// ------------------------------------------------------------------ tiles

/** A tile that's one big round button, opening [target]. */
abstract class ButtonTile : TileService() {
    abstract val title: String
    abstract fun line(): String
    abstract val target: Class<out Activity>
    abstract val glyph: String
    abstract val color: Long

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> =
        CallbackToFutureAdapter.getFuture { done ->
            val look = WearLooks.current(this)
            val click = ModifiersBuilders.Clickable.Builder().setId("open").setOnClick(
                ActionBuilders.LaunchAction.Builder().setAndroidActivity(
                    ActionBuilders.AndroidActivity.Builder().setPackageName(packageName).setClassName(target.name).build()).build()).build()
            fun text(s: String, size: Float, color: Long, italic: Boolean = false) = LayoutElementBuilders.Text.Builder().setText(s).setMaxLines(2)
                .setFontStyle(LayoutElementBuilders.FontStyle.Builder().setSize(sp(size)).setColor(argb(color.toInt())).setItalic(italic).build()).build()
            val disc = LayoutElementBuilders.Box.Builder().setWidth(dp(78f)).setHeight(dp(78f))
                .setModifiers(ModifiersBuilders.Modifiers.Builder().setClickable(click)
                    .setBackground(ModifiersBuilders.Background.Builder().setColor(argb(color.toInt()))
                        .setCorner(ModifiersBuilders.Corner.Builder().setRadius(dp(39f)).build()).build())
                    .setSemantics(ModifiersBuilders.Semantics.Builder().setContentDescription(title).build()).build())
                .addContent(text(glyph, 30f, 0xFF14100C)).build()
            val col = LayoutElementBuilders.Column.Builder().setHorizontalAlignment(LayoutElementBuilders.HORIZONTAL_ALIGN_CENTER)
                .addContent(text(title, 14f, look.lore, italic = true))
                .addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(8f)).build())
                .addContent(disc)
                .addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(8f)).build())
                .addContent(text(line(), 12f, look.soft))
            val root = LayoutElementBuilders.Box.Builder().setWidth(expand()).setHeight(expand())
                .setModifiers(ModifiersBuilders.Modifiers.Builder().setBackground(ModifiersBuilders.Background.Builder().setColor(argb(look.tileBackground.toInt())).build()).build())
                .addContent(col.build()).build()
            done.set(TileBuilders.Tile.Builder().setResourcesVersion("1").setFreshnessIntervalMillis(60_000L)
                .setTileTimeline(TimelineBuilders.Timeline.fromLayoutElement(root)).build())
            "lembas-button-tile"
        }

    override fun onTileResourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ListenableFuture<ResourceBuilders.Resources> =
        CallbackToFutureAdapter.getFuture { done -> done.set(ResourceBuilders.Resources.Builder().setVersion(requestParams.version).build()); "lembas-button-tile-resources" }
}

class HornTile : ButtonTile() {
    override val title = "Horn of Gondor"
    override fun line() = "Find your phone"
    override val target = HornActivity::class.java
    override val glyph = "📯"
    override val color = 0xFFE2C46F
}

class PhialTile : ButtonTile() {
    override val title = "Phial of Galadriel"
    override fun line() = "A soft starlight torch"
    override val target = PhialActivity::class.java
    override val glyph = "✦"
    override val color = 0xFFDDE7FF
}

class FocusTile : ButtonTile() {
    override val title = "Smoke-ring focus"
    override fun line() = Touches.focusEnd(this).let { if (it > 0) "${(it - System.currentTimeMillis()) / 60_000 + 1} min to go" else "25 minutes, then a ring" }
    override val target = FocusActivity::class.java
    override val glyph = "◯"
    override val color = 0xFFDAC696
}
