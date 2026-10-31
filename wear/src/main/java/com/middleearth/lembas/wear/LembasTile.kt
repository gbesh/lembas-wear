package com.middleearth.lembas.wear

import android.content.ComponentName
import android.content.Context
import android.content.pm.LauncherApps
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Process
import androidx.concurrent.futures.CallbackToFutureAdapter
import androidx.wear.protolayout.ActionBuilders
import androidx.wear.protolayout.ColorBuilders.argb
import androidx.wear.protolayout.DimensionBuilders.dp
import androidx.wear.protolayout.DimensionBuilders.expand
import androidx.wear.protolayout.DimensionBuilders.sp
import androidx.wear.protolayout.DimensionBuilders.wrap
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

/**
 * The Lembas tile: the Shire date, the mealtime and when the look next changes, in the look's colours, with
 * your four most recent apps one tap away, and a button for the full list.
 * It refreshes every quarter of an hour, and when you open an app from Lembas.
 */
class LembasTile : TileService() {

    /** Your favourites first, then your latest apps, four in all. */
    private fun recentComponents(): List<ComponentName> =
        (Apps.favouriteKeys(this) + Apps.recentKeys(this)).distinct().mapNotNull { ComponentName.unflattenFromString(it) }.take(4)

    /** "Alarm 6:30" when an alarm is due in the next 12 hours, otherwise the mealtime. */
    private fun subtitle(now: LocalDateTime): String {
        try {
            val next = getSystemService(android.app.AlarmManager::class.java)?.nextAlarmClock
            if (next != null) {
                val t = java.time.Instant.ofEpochMilli(next.triggerTime).atZone(java.time.ZoneId.systemDefault()).toLocalDateTime()
                if (java.time.Duration.between(now, t).toHours() < 12) {
                    val h24 = android.text.format.DateFormat.is24HourFormat(this)
                    return "Alarm " + t.format(java.time.format.DateTimeFormatter.ofPattern(if (h24) "H:mm" else "h:mm a"))
                }
            }
        } catch (_: Throwable) { }
        return Lore.meal(now.hour)
    }

    private fun resourcesVersion(): String = recentComponents().joinToString("|") { it.flattenToShortString() }.hashCode().toString()

    override fun onTileRequest(requestParams: RequestBuilders.TileRequest): ListenableFuture<TileBuilders.Tile> =
        CallbackToFutureAdapter.getFuture { done ->
            val now = LocalDateTime.now()
            val look = WearLooks.current(this, now)
            val tile = TileBuilders.Tile.Builder()
                .setResourcesVersion(resourcesVersion())
                .setFreshnessIntervalMillis(15 * 60 * 1000L)
                .setTileTimeline(TimelineBuilders.Timeline.fromLayoutElement(layout(look, now)))
                .build()
            done.set(tile)
            "lembas-tile"
        }

    override fun onTileResourcesRequest(requestParams: RequestBuilders.ResourcesRequest): ListenableFuture<ResourceBuilders.Resources> =
        CallbackToFutureAdapter.getFuture { done ->
            val res = ResourceBuilders.Resources.Builder().setVersion(resourcesVersion())
            val la = getSystemService(LauncherApps::class.java)
            val size = (36 * resources.displayMetrics.density).toInt()
            recentComponents().forEachIndexed { i, c ->
                try {
                    val info = la?.getActivityList(c.packageName, Process.myUserHandle())?.firstOrNull { it.componentName == c } ?: return@forEachIndexed
                    val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
                    val d = info.getBadgedIcon(0)
                    d.setBounds(0, 0, size, size)
                    d.draw(Canvas(bmp))
                    val png = ByteArrayOutputStream().also { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }.toByteArray()
                    res.addIdToImageMapping("app$i", ResourceBuilders.ImageResource.Builder()
                        .setInlineResource(ResourceBuilders.InlineImageResource.Builder()
                            .setData(png).setWidthPx(size).setHeightPx(size)
                            .setFormat(ResourceBuilders.IMAGE_FORMAT_UNDEFINED).build())
                        .build())
                } catch (_: Exception) { }
            }
            done.set(res.build())
            "lembas-tile-resources"
        }

    private fun text(s: String, size: Float, color: Long, italic: Boolean = false): LayoutElementBuilders.Text =
        LayoutElementBuilders.Text.Builder()
            .setText(s)
            .setMaxLines(1)
            .setFontStyle(LayoutElementBuilders.FontStyle.Builder()
                .setSize(sp(size))
                .setColor(argb(color.toInt()))
                .setItalic(italic)
                .build())
            .build()

    private fun launch(c: ComponentName): ModifiersBuilders.Clickable =
        ModifiersBuilders.Clickable.Builder()
            .setId(c.flattenToShortString())
            .setOnClick(ActionBuilders.LaunchAction.Builder()
                .setAndroidActivity(ActionBuilders.AndroidActivity.Builder()
                    .setPackageName(c.packageName).setClassName(c.className).build())
                .build())
            .build()

    private fun layout(look: WearLook, now: LocalDateTime): LayoutElementBuilders.LayoutElement {
        val bg = look.tileBackground
        val col = LayoutElementBuilders.Column.Builder()
            .setHorizontalAlignment(LayoutElementBuilders.HORIZONTAL_ALIGN_CENTER)
            .addContent(text(Lore.shireWeekday(now.dayOfWeek).uppercase(), 12f, look.accent))
            .addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(2f)).build())
            .addContent(text(Lore.shireDate(now.toLocalDate()), 17f, look.lore, italic = true))
            .addContent(text(subtitle(now), 13f, look.soft, italic = true))
        // when the look changes next, so you know what's coming ("Starlit Night at 7:21 pm")
        WearLooks.next(this, now)?.let { (next, at) ->
            val h24 = android.text.format.DateFormat.is24HourFormat(this)
            col.addContent(text("${next.title} at " + at.format(java.time.format.DateTimeFormatter.ofPattern(if (h24) "H:mm" else "h:mm a")), 11f, look.lore))
        }
        col.addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(10f)).build())

        val recents = recentComponents()
        if (recents.isNotEmpty()) {
            val row = LayoutElementBuilders.Row.Builder().setVerticalAlignment(LayoutElementBuilders.VERTICAL_ALIGN_CENTER)
            recents.forEachIndexed { i, c ->
                if (i > 0) row.addContent(LayoutElementBuilders.Spacer.Builder().setWidth(dp(6f)).build())
                row.addContent(LayoutElementBuilders.Box.Builder()
                    .setWidth(dp(42f)).setHeight(dp(42f))
                    .setModifiers(ModifiersBuilders.Modifiers.Builder()
                        .setClickable(launch(c))
                        .setBackground(ModifiersBuilders.Background.Builder()
                            .setColor(argb(look.surface.toInt()))
                            .setCorner(ModifiersBuilders.Corner.Builder().setRadius(dp(21f)).build())
                            .build())
                        .build())
                    .addContent(LayoutElementBuilders.Image.Builder().setResourceId("app$i").setWidth(dp(32f)).setHeight(dp(32f)).build())
                    .build())
            }
            col.addContent(row.build())
            col.addContent(LayoutElementBuilders.Spacer.Builder().setHeight(dp(10f)).build())
        }

        // "All apps" opens the Lembas list
        col.addContent(LayoutElementBuilders.Box.Builder()
            .setWidth(wrap()).setHeight(dp(32f))
            .setModifiers(ModifiersBuilders.Modifiers.Builder()
                .setClickable(launch(ComponentName(this, MainActivity::class.java)))
                .setBackground(ModifiersBuilders.Background.Builder()
                    .setColor(argb(look.accent.toInt()))
                    .setCorner(ModifiersBuilders.Corner.Builder().setRadius(dp(16f)).build())
                    .build())
                .setPadding(ModifiersBuilders.Padding.Builder().setStart(dp(16f)).setEnd(dp(16f)).build())
                .build())
            .addContent(text("All apps", 14f, bg))
            .build())

        return LayoutElementBuilders.Box.Builder()
            .setWidth(expand()).setHeight(expand())
            .setModifiers(ModifiersBuilders.Modifiers.Builder()
                .setBackground(ModifiersBuilders.Background.Builder().setColor(argb(bg.toInt())).build())
                .build())
            .addContent(col.build())
            .build()
    }

    companion object {
        fun refresh(ctx: Context) {
            try { getUpdater(ctx).requestUpdate(LembasTile::class.java) } catch (_: Exception) { }
        }
    }
}
