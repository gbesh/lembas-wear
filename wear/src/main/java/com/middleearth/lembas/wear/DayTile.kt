package com.middleearth.lembas.wear

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.RectF
import androidx.concurrent.futures.CallbackToFutureAdapter
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
import com.google.common.util.concurrent.ListenableFuture
import java.io.ByteArrayOutputStream
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import kotlin.math.cos
import kotlin.math.sin

/** Your day at a glance: today's sun arc with the sun on it, sunrise and sunset, and the next look. */
class DayTile : TileService() {
    private fun hm(m: Int): String = java.time.LocalTime.of((m / 60).coerceIn(0, 23), m % 60)
        .format(DateTimeFormatter.ofPattern(if (android.text.format.DateFormat.is24HourFormat(this)) "H:mm" else "h:mm a"))

    private fun arc(look: WearLook, now: LocalDateTime): ByteArray {
        val w = 320; val h = 150
        val bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888)
        val c = Canvas(bmp)
        val day = Sun.today(ZoneId.systemDefault(), now.toLocalDate())
        val p = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.STROKE; strokeWidth = 6f; strokeCap = Paint.Cap.ROUND }
        val box = RectF(20f, 20f, w - 20f, (h - 10f) * 2 - 20f)
        p.color = ((look.soft and 0x00FFFFFFL) or 0x55000000L).toInt(); c.drawArc(box, 180f, 180f, false, p)
        val m = now.hour * 60 + now.minute
        val f = ((m - day.sunrise).toFloat() / (day.sunset - day.sunrise).coerceAtLeast(1)).coerceIn(0f, 1f)
        p.color = look.accent.toInt(); c.drawArc(box, 180f, 180f * f, false, p)
        if (m in day.sunrise..day.sunset) {
            val a = Math.PI * (1 - f)
            val cx = box.centerX() + box.width() / 2 * cos(a).toFloat(); val cy = box.centerY() - box.height() / 2 * sin(a).toFloat()
            val s = Paint(Paint.ANTI_ALIAS_FLAG).apply { color = 0xFFFFD86A.toInt() }
            s.alpha = 70; c.drawCircle(cx, cy, 22f, s); s.alpha = 255; c.drawCircle(cx, cy, 11f, s)
        }
        return ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
    }

    private fun text(s: String, size: Float, color: Long, italic: Boolean = false) = LayoutElementBuilders.Text.Builder().setText(s).setMaxLines(1)
        .setFontStyle(LayoutElementBuilders.FontStyle.Builder().setSize(sp(size)).setColor(argb(color.toInt())).setItalic(italic).build()).build()

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> =
        CallbackToFutureAdapter.getFuture { done ->
            val now = LocalDateTime.now()
            val look = WearLooks.current(this, now)
            val day = Sun.today(ZoneId.systemDefault(), now.toLocalDate())
            val col = LayoutElementBuilders.Column.Builder().setHorizontalAlignment(LayoutElementBuilders.HORIZONTAL_ALIGN_CENTER)
                .addContent(text(Lore.shireDate(now.toLocalDate()), 14f, look.lore, italic = true))
                .addContent(LayoutElementBuilders.Image.Builder().setResourceId("arc").setWidth(dp(150f)).setHeight(dp(70f)).build())
                .addContent(text("Sunrise ${hm(day.sunrise)} · Sunset ${hm(day.sunset)}", 13f, look.text))
            WearLooks.next(this, now)?.let { (next, at) ->
                col.addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(4f)).build())
                col.addContent(text("${next.title} at ${hm(at.hour * 60 + at.minute)}", 12f, look.soft))
            }
            val root = LayoutElementBuilders.Box.Builder().setWidth(expand()).setHeight(expand())
                .setModifiers(ModifiersBuilders.Modifiers.Builder()
                    .setBackground(ModifiersBuilders.Background.Builder().setColor(argb(look.tileBackground.toInt())).build()).build())
                .addContent(col.build()).build()
            done.set(TileBuilders.Tile.Builder().setResourcesVersion("${look.id}-${now.hour}-${now.minute / 15}")
                .setFreshnessIntervalMillis(15 * 60 * 1000L)
                .setTileTimeline(TimelineBuilders.Timeline.fromLayoutElement(root)).build())
            "lembas-day-tile"
        }

    override fun onTileResourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ListenableFuture<ResourceBuilders.Resources> =
        CallbackToFutureAdapter.getFuture { done ->
            val now = LocalDateTime.now()
            val look = WearLooks.current(this, now)
            done.set(ResourceBuilders.Resources.Builder().setVersion(requestParams.version)
                .addIdToImageMapping("arc", ResourceBuilders.ImageResource.Builder()
                    .setInlineResource(ResourceBuilders.InlineImageResource.Builder().setData(arc(look, now))
                        .setWidthPx(320).setHeightPx(150).setFormat(ResourceBuilders.IMAGE_FORMAT_UNDEFINED).build()).build())
                .build())
            "lembas-day-tile-resources"
        }
}
