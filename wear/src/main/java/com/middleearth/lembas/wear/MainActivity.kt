package com.middleearth.lembas.wear

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.LauncherApps
import android.graphics.Bitmap
import android.graphics.Canvas
import android.net.Uri
import android.os.Bundle
import android.os.Process
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.wear.compose.foundation.lazy.TransformingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.foundation.lazy.rememberTransformingLazyColumnState
import androidx.wear.compose.material3.AppScaffold
import androidx.wear.compose.material3.Button
import androidx.wear.compose.material3.ButtonDefaults
import androidx.wear.compose.material3.ColorScheme
import androidx.wear.compose.material3.ListHeader
import androidx.wear.compose.material3.MaterialTheme
import androidx.wear.compose.material3.ScreenScaffold
import androidx.wear.compose.material3.Text
import androidx.wear.tiles.TileService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/**
 * Lembas on the watch: your apps in the look of the hour. Lately at the top, then everything
 * A–Z; turn the crown (or swipe) to scroll. Long-press an app for its info page.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WearUpdater.schedule(this)
        setContent { LembasApp() }
    }

    override fun onResume() {
        super.onResume()
        WearUpdater.showPending(this)
    }
}

class AppItem(val label: String, val component: ComponentName, val icon: ImageBitmap)

object Apps {
    private const val PREF_RECENT = "recent"

    fun load(ctx: Context): List<AppItem> {
        val la = ctx.getSystemService(LauncherApps::class.java) ?: return emptyList()
        val size = (40 * ctx.resources.displayMetrics.density).toInt()
        return la.getActivityList(null, Process.myUserHandle())
            .filter { it.componentName.packageName != ctx.packageName }
            .map { info ->
                val d = info.getBadgedIcon(0)
                val bmp = Bitmap.createBitmap(size, size, Bitmap.Config.ARGB_8888)
                d.setBounds(0, 0, size, size)
                d.draw(Canvas(bmp))
                AppItem(info.label.toString(), info.componentName, bmp.asImageBitmap())
            }
            .sortedBy { it.label.lowercase() }
    }

    fun recentKeys(ctx: Context): List<String> =
        (ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).getString(PREF_RECENT, "") ?: "")
            .split('\n').filter { it.isNotEmpty() }

    fun launch(ctx: Context, app: AppItem) {
        val key = app.component.flattenToString()
        val keys = (listOf(key) + recentKeys(ctx).filter { it != key }).take(8)
        ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).edit().putString(PREF_RECENT, keys.joinToString("\n")).apply()
        try {
            ctx.getSystemService(LauncherApps::class.java)
                ?.startMainActivity(app.component, Process.myUserHandle(), null, null)
        } catch (_: Exception) {
            Toast.makeText(ctx, "Couldn't open ${app.label}", Toast.LENGTH_SHORT).show()
        }
        // The tile shows recent apps: let it refresh
        try { TileService.getUpdater(ctx).requestUpdate(LembasTile::class.java) } catch (_: Exception) { }
    }

    fun info(ctx: Context, app: AppItem) {
        try {
            ctx.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${app.component.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: Exception) { }
    }
}

private fun Long.c() = Color(this.toInt())

private fun scheme(look: WearLook): ColorScheme {
    val accent = look.accent.c()
    val surface = look.surface.c()
    return ColorScheme(
        primary = accent,
        onPrimary = if (look.dark) Color(0xFF101010) else Color(0xFFFFFBF2),
        primaryContainer = surface,
        onPrimaryContainer = look.onSurface.c(),
        surfaceContainer = surface,
        onSurface = look.text.c(),
        onSurfaceVariant = look.soft.c(),
        background = if (look.dark) Color.Black else Color(0xFFF6EFDD),
        onBackground = look.text.c(),
    )
}

@Composable
fun LembasApp() {
    val ctx = LocalContext.current
    var now by remember { mutableStateOf(LocalDateTime.now()) }
    var choiceTick by remember { mutableIntStateOf(0) }
    LaunchedEffect(Unit) {
        while (true) {
            val n = LocalDateTime.now()
            delay(((60 - n.second) * 1000L - n.nano / 1_000_000).coerceAtLeast(1000))
            now = LocalDateTime.now()
        }
    }
    val look = remember(now.hour, now.minute / 5, choiceTick) { WearLooks.current(ctx, now) }
    val apps by produceState(initialValue = emptyList<AppItem>()) { value = withContext(Dispatchers.Default) { Apps.load(ctx) } }
    val recents = remember(apps, now) {
        val byKey = apps.associateBy { it.component.flattenToString() }
        Apps.recentKeys(ctx).mapNotNull { byKey[it] }.take(4)
    }
    val serif = remember(look) { FontFamily(Font(look.serif)) }
    val italic = remember(look) { FontFamily(Font(look.italic, style = FontStyle.Italic)) }
    val label = remember(look) { FontFamily(Font(look.label)) }

    MaterialTheme(colorScheme = scheme(look)) {
        AppScaffold {
            val state = rememberTransformingLazyColumnState()
            ScreenScaffold(scrollState = state) { padding ->
                Box(Modifier.fillMaxSize().background(if (look.dark) Color.Black else Color(0xFFF6EFDD))) {
                    Image(painterResource(look.background), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                    // A veil so the list stays readable over the scene
                    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(
                        if (look.dark) listOf(Color(0x00000000), Color(0x66000000), Color(0xAA000000))
                        else listOf(Color(0x00FFFFFF), Color(0x55FFF8EA), Color(0x99FFF8EA)))))
                    TransformingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxSize()) {
                        item { Header(look, now, serif, italic, label) }
                        if (recents.isNotEmpty()) {
                            item { ListHeader { Text("Lately", fontFamily = label, color = look.accent.c()) } }
                            items(recents, key = { "r" + it.component.flattenToString() }) { app -> AppButton(look, app) }
                        }
                        item { ListHeader { Text(if (apps.isEmpty()) "Gathering your apps…" else "All apps", fontFamily = label, color = look.accent.c()) } }
                        items(apps, key = { it.component.flattenToString() }) { app -> AppButton(look, app) }
                        item { ListHeader { Text("Lembas", fontFamily = label, color = look.accent.c()) } }
                        item {
                            val choice = WearLooks.choice(ctx)
                            SettingButton(look, "Look", if (choice == WearLook.AUTO) "Follows the sun (now ${look.title})" else look.title) {
                                val order = listOf(WearLook.AUTO) + WearLook.ALL.map { it.id }
                                WearLooks.setChoice(ctx, order[(order.indexOf(choice) + 1) % order.size])
                                choiceTick++
                            }
                        }
                        item {
                            SettingButton(look, "Watch face & updates", "Version ${WearUpdater.versionName(ctx)}") {
                                WearUpdater.checkNow(ctx)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Header(look: WearLook, now: LocalDateTime, serif: FontFamily, italic: FontFamily, label: FontFamily) {
    val h24 = android.text.format.DateFormat.is24HourFormat(LocalContext.current)
    val time = now.format(DateTimeFormatter.ofPattern(if (h24) "H:mm" else "h:mm"))
    Column(Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(Lore.quenya(now.hour).uppercase(), fontFamily = label, fontSize = 11.sp, letterSpacing = 2.sp, color = look.accent.c())
        Text(time, fontFamily = serif, fontSize = 44.sp, color = look.text.c(), maxLines = 1)
        Text("${Lore.shireWeekday(now.dayOfWeek)}, ${Lore.shireDate(now.toLocalDate())}", fontFamily = italic, fontStyle = FontStyle.Italic,
            fontSize = 14.sp, color = if (look.dark) look.accent.c() else look.text.c(), textAlign = TextAlign.Center)
        Text(Lore.meal(now.hour), fontFamily = italic, fontStyle = FontStyle.Italic, fontSize = 12.sp, color = look.soft.c())
    }
}

@Composable
private fun AppButton(look: WearLook, app: AppItem) {
    val ctx = LocalContext.current
    Button(
        onClick = { Apps.launch(ctx, app) },
        onLongClick = { Apps.info(ctx, app) },
        onLongClickLabel = "App info",
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = look.surface.c(), contentColor = look.onSurface.c()),
        icon = {
            Image(app.icon, null, Modifier.size(28.dp).clip(CircleShape).border(1.dp, look.ring.c(), CircleShape))
        },
        label = { Text(app.label, maxLines = 1, overflow = TextOverflow.Ellipsis) },
    )
}

@Composable
private fun SettingButton(look: WearLook, title: String, detail: String, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = look.surface.c(), contentColor = look.onSurface.c(),
            secondaryContentColor = look.soft.c()),
        secondaryLabel = { Text(detail, maxLines = 2) },
        label = { Text(title) },
    )
}
