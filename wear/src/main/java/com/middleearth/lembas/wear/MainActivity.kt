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
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
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

    private const val PREF_FAVOURITES = "favourites"

    fun favouriteKeys(ctx: Context): List<String> =
        (ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).getString(PREF_FAVOURITES, "") ?: "")
            .split('\n').filter { it.isNotEmpty() }

    fun isFavourite(ctx: Context, app: AppItem) = app.component.flattenToString() in favouriteKeys(ctx)

    /** Pin or unpin; favourites sit at the top of the list and on the tile. */
    fun toggleFavourite(ctx: Context, app: AppItem): Boolean {
        val key = app.component.flattenToString()
        val now = favouriteKeys(ctx)
        val pinned = key !in now
        val keys = if (pinned) (now + key).take(8) else now - key
        ctx.getSharedPreferences("lembas", Context.MODE_PRIVATE).edit().putString(PREF_FAVOURITES, keys.joinToString("\n")).apply()
        try { TileService.getUpdater(ctx).requestUpdate(LembasTile::class.java) } catch (_: Exception) { }
        return pinned
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
    val surface = look.surface.c()
    return ColorScheme(
        primary = look.accent.c(),
        onPrimary = Color(0xFF101010),
        primaryContainer = surface,
        onPrimaryContainer = look.text.c(),
        surfaceContainer = surface,
        onSurface = look.text.c(),
        onSurfaceVariant = look.soft.c(),
        background = Color.Black,
        onBackground = look.text.c(),
    )
}

/** The watch face's type: heavy and light numerals, an italic for the lore, a clean sans for labels. */
private class Type(
    val heavy: FontFamily = FontFamily(Font(R.font.numerals_heavy)),
    val light: FontFamily = FontFamily(Font(R.font.numerals_light)),
    val lore: FontFamily = FontFamily(Font(R.font.lore_italic, style = FontStyle.Italic)),
    val label: FontFamily = FontFamily(Font(R.font.alegreya_sans)),
)

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
    val type = remember { Type() }
    var favTick by remember { mutableIntStateOf(0) }
    val favourites = remember(apps, favTick) {
        val byKey = apps.associateBy { it.component.flattenToString() }
        Apps.favouriteKeys(ctx).mapNotNull { byKey[it] }
    }
    var menuFor by remember { mutableStateOf<AppItem?>(null) }

    MaterialTheme(colorScheme = scheme(look)) {
        AppScaffold {
            val state = rememberTransformingLazyColumnState()
            // the first letter of the app at the top of the A-Z list, shown while you scroll
            // list order: header, [Favourites heading + apps], [Lately heading + apps], "All apps" heading, then A-Z
            val firstApp = 2 + (if (favourites.isNotEmpty()) 1 + favourites.size else 0) + (if (recents.isNotEmpty()) 1 + recents.size else 0)
            val letter by remember(apps, firstApp) {
                derivedStateOf {
                    val mid = state.layoutInfo.visibleItems.getOrNull(state.layoutInfo.visibleItems.size / 2)?.index ?: -1
                    apps.getOrNull(mid - firstApp)?.label?.firstOrNull()?.uppercaseChar()?.toString() ?: ""
                }
            }
            ScreenScaffold(scrollState = state) { padding ->
                Box(Modifier.fillMaxSize().background(Color.Black)) {
                    Image(painterResource(look.background), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
                    // the scene softly veiled, darker further down, so the list stays calm and readable
                    Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0x59000000), Color(0xA6000000), Color(0xE0000000)))))
                    TransformingLazyColumn(state = state, contentPadding = padding, modifier = Modifier.fillMaxSize()) {
                        item { Header(look, now, type) }
                        if (favourites.isNotEmpty()) {
                            item { Heading(look, type, "Favourites") }
                            items(favourites, key = { "f" + it.component.flattenToString() }) { app -> AppButton(look, app) { menuFor = app } }
                        }
                        if (recents.isNotEmpty()) {
                            item { Heading(look, type, "Lately") }
                            items(recents, key = { "r" + it.component.flattenToString() }) { app -> AppButton(look, app) { menuFor = app } }
                        }
                        item { Heading(look, type, if (apps.isEmpty()) "Gathering your apps…" else "All apps") }
                        items(apps, key = { it.component.flattenToString() }) { app -> AppButton(look, app) { menuFor = app } }
                        item { Heading(look, type, "Lembas") }
                        item {
                            LookSwatches(look, WearLooks.choice(ctx)) { id ->
                                WearLooks.setChoice(ctx, id)
                                choiceTick++
                            }
                        }
                        item {
                            var chime by remember { mutableStateOf(Chime.mode(ctx)) }
                            SettingButton(look, "Tap on the wrist", Chime.label(chime)) {
                                chime = Chime.next(chime); Chime.setMode(ctx, chime)
                            }
                        }
                        item {
                            SettingButton(look, "Watch face & updates", "Version ${WearUpdater.versionName(ctx)}") {
                                WearUpdater.checkNow(ctx)
                            }
                        }
                    }
                    // the letter guide
                    if (state.isScrollInProgress && letter.isNotEmpty()) {
                        Box(Modifier.align(Alignment.CenterEnd).padding(end = 14.dp).size(44.dp).clip(CircleShape)
                            .background(look.surface.c()), contentAlignment = Alignment.Center) {
                            Text(letter, fontFamily = type.heavy, fontSize = 24.sp, color = look.accent.c())
                        }
                    }
                    menuFor?.let { app ->
                        AppMenu(look, type, app, Apps.isFavourite(ctx, app),
                            onPin = { val pinned = Apps.toggleFavourite(ctx, app); favTick++; menuFor = null
                                Toast.makeText(ctx, if (pinned) "Pinned to Favourites" else "Unpinned", Toast.LENGTH_SHORT).show() },
                            onInfo = { Apps.info(ctx, app); menuFor = null },
                            onClose = { menuFor = null })
                    }
                }
            }
        }
    }
}

/** Follow the sun, or one look: tap a swatch. */
@Composable
private fun LookSwatches(look: WearLook, choice: String, onPick: (String) -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(if (choice == WearLook.AUTO) "Look: follows the sun (now ${look.title})" else "Look: ${look.title}",
            fontSize = 13.sp, color = look.text.c(), textAlign = TextAlign.Center)
        Row(Modifier.padding(top = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            val options = listOf(WearLook.AUTO to null) + WearLook.ALL.map { it.id to it }
            options.forEach { (id, l) ->
                val selected = id == choice
                Box(Modifier.padding(horizontal = 3.dp).size(if (selected) 30.dp else 26.dp).clip(CircleShape)
                    .background(if (l == null) Brush.sweepGradient(WearLook.ALL.map { it.accent.c() } + WearLook.SHIRE.accent.c())
                        else Brush.linearGradient(listOf(l.accent.c(), l.surface.c())))
                    .border(if (selected) 2.dp else 0.dp, if (selected) look.text.c() else Color.Transparent, CircleShape)
                    .clickable { onPick(id) })
            }
        }
    }
}

@Composable
private fun AppMenu(look: WearLook, type: Type, app: AppItem, favourite: Boolean, onPin: () -> Unit, onInfo: () -> Unit, onClose: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Color(0xE6000000)).clickable { onClose() }, contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(horizontal = 28.dp)) {
            Image(app.icon, null, Modifier.size(36.dp).clip(CircleShape))
            Text(app.label, fontFamily = type.label, fontSize = 15.sp, color = look.text.c(), maxLines = 1, overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = 4.dp, bottom = 8.dp))
            SettingButton(look, if (favourite) "Unpin" else "Pin to Favourites", "", onPin)
            Spacer(Modifier.height(4.dp))
            SettingButton(look, "App info", "", onInfo)
        }
    }
}

@Composable
private fun Heading(look: WearLook, type: Type, title: String) {
    ListHeader { Text(title.uppercase(), fontFamily = type.label, fontSize = 13.sp, letterSpacing = 1.5.sp, color = look.accent.c()) }
}

@Composable
private fun Header(look: WearLook, now: LocalDateTime, type: Type) {
    val h24 = android.text.format.DateFormat.is24HourFormat(LocalContext.current)
    val hours = now.format(DateTimeFormatter.ofPattern(if (h24) "HH" else "hh"))
    val minutes = now.format(DateTimeFormatter.ofPattern("mm"))
    val date = now.format(DateTimeFormatter.ofPattern("EEE d"))
    Column(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(date, fontFamily = type.label, fontSize = 14.sp, color = look.text.c())
        Text("${Lore.shireWeekday(now.dayOfWeek)} · ${Lore.shireDate(now.toLocalDate())}", fontFamily = type.lore, fontStyle = FontStyle.Italic,
            fontSize = 13.sp, color = look.lore.c(), textAlign = TextAlign.Center, maxLines = 1)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(hours, fontFamily = type.heavy, fontSize = 50.sp, color = look.accent.c(), maxLines = 1)
            Spacer(Modifier.width(6.dp))
            Text(minutes, fontFamily = type.light, fontSize = 50.sp, color = look.text.c(), maxLines = 1)
        }
        Text(Lore.meal(now.hour), fontFamily = type.lore, fontStyle = FontStyle.Italic, fontSize = 12.sp, color = look.soft.c())
    }
}

@Composable
private fun AppButton(look: WearLook, app: AppItem, onMenu: () -> Unit) {
    val ctx = LocalContext.current
    Button(
        onClick = { Apps.launch(ctx, app) },
        onLongClick = onMenu,
        onLongClickLabel = "Pin or app info",
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = look.surface.c(), contentColor = look.text.c()),
        icon = { Image(app.icon, null, Modifier.size(30.dp).clip(CircleShape)) },
        label = { Text(app.label, maxLines = 1, overflow = TextOverflow.Ellipsis) },
    )
}

@Composable
private fun SettingButton(look: WearLook, title: String, detail: String, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        colors = ButtonDefaults.buttonColors(containerColor = look.surface.c(), contentColor = look.text.c(),
            secondaryContentColor = look.soft.c()),
        secondaryLabel = if (detail.isEmpty()) null else ({ Text(detail, maxLines = 2) }),
        label = { Text(title) },
    )
}
