# Lembas for Wear OS — a Middle-earth watch face and launcher

*One small bite is enough.* The four Lembas looks, made for a round watch: a watch face that follows the sun, a launcher app in the look of the hour, and a tile.

Built and tested for the Pixel Watch (Wear OS 5 or later); it should work on any round Wear OS 5+ watch.

The phone launcher lives in **[gbesh/lembas-android](https://github.com/gbesh/lembas-android)** and the Windows version in **[gbesh/lembas-windows](https://github.com/gbesh/lembas-windows)**.

## Install (once)

**From your phone (easiest, no computer).** With the Lembas phone launcher ([gbesh/lembas-android](https://github.com/gbesh/lembas-android)) on an Android 11+ phone on the same Wi-Fi as the watch:

1. On the watch, turn on Developer options: Settings → System → About → Versions, tap **Build number** 7 times.
2. In Settings → Developer options, turn on **ADB debugging** and **Wireless debugging**, then open Wireless debugging → **Pair new device**.
3. On the phone, long-press the home screen → **Put Lembas on your watch**, and type the six-digit code the watch shows. The phone finds the watch, pairs, and installs the watch app and the watch face.

**From a Windows PC.** Download **`Lembas-watch-installer.zip`** from the [latest release](https://github.com/gbesh/lembas-wear/releases/latest), unzip it, double-click **Install Lembas on your watch**, and follow it (steps 1 and 2 above, then the addresses and code the watch shows).

Then **add the face:** touch and hold the watch face, swipe to the end, tap **+** and choose **Lembas**; and **add the tile:** swipe left from the face and add the **Lembas** tile. You can turn Wireless debugging off again afterwards.

## Updates

The watch app keeps itself and the watch face up to date from this repo's latest release. It checks once a day, **only while the watch is charging**, so it costs nothing during the day. To update straight away, open Lembas and tap **Watch face & updates** at the bottom.

Every push to `main` builds a new release. Releases are signed with the same key as every earlier Lembas watch build (kept in the repo's Actions secrets, never in the code), so each one installs over the last.

**Installed before the move?** The watch builds used to be published in gbesh/lembas-android, and those builds still look there for updates. Run **`wear/install/Move from lembas-android (once).cmd`** on a Windows PC once: it removes the old watch app and watch face, installs the current ones from here, and from then on they update from this repo. Removing the old version takes the face and tile off the watch, so add them back afterwards. (Installing from the phone does the same job.)

## The watch face

Four flat, colourful little scenes, drawn to match Lembas on the phone and the PC, that follow the sun:

| Look | When (Follow the sun) | The scene |
|---|---|---|
| **Shire Morning** | sunrise → late afternoon | Green hills, the round green door, a low sun and chimney smoke |
| **Red Book** | late afternoon → sunset | A crackling fire on deep red, embers rising |
| **Starlit Night** | sunset → 11pm, 4am → sunrise | Violet mountains, a cabin with a lit window, tonight's real moon and the odd shooting star |
| **Elven Silver** | 11pm → 4am | Two silver trees of Rivendell on a teal knoll, Eärendil's star, motes of light drifting up |

- **The seasons:** blossom in spring, golden hills and leaves in autumn, snow in winter (snow on the mountains, bare silver trees), worked out from the month and flipped south of the equator.
- **The weather**, from the watch's own forecast: drifting cloud, fog, falling rain or snow over the scene (never indoors by the fire).
- **Large stacked numerals** (Fraunces): the hours heavy, the minutes light; the date and the **Shire date** above (*Sat 31 · 10 Blotmath*) and the **hobbit mealtime** below (*Second breakfast*, *Afternoon tea*, … *The Shire sleeps*).
- **Two complications**, either side of the time (battery and steps by default). Touch and hold the face → Customise to change them.
- **Tap** the time for alarms, and the date or the mealtime for the Lembas app.

**The same clock everywhere:** the face works out sunrise, late afternoon (the sun down to 15°) and sunset for your time zone's main city with exactly the same sums and cities as the phone launcher, the watch app and Lembas for Windows, so all of them change look at the same minute. (In a time zone Lembas doesn't know, it falls back to the watch's weather data for day and night.) Touch and hold → Customise picks one look to keep instead.

**Always-on display:** the scene drawn as fine grey lines, with the time in thin numerals and the date. It all drifts a few pixels each minute so no pixel stays lit for hours.

**Light on the battery:** only small things move (a glow, smoke, flames, a few stars and motes, the weather). The animation values change at most once a second and the watch glides between them at 8–12 frames per second; rain and snow are short 8-frame loops. Everything stops in ambient mode. The pictures are flat colour in 256-colour palettes, so the whole face is under a megabyte.

## The watch app and tile

- **Lembas** (in the app list), in the same type and colours as the face: the date, the Shire date, the time (hours heavy, minutes light) and the mealtime, then **Favourites**, **Lately** (your four latest apps) and **All apps** A–Z. Turn the crown to scroll; a letter shows where you are in the alphabet while you do. **Touch and hold** an app to pin it to Favourites or open its info. At the bottom: the **look** (tap a swatch: follow the sun, or one look) and **Watch face & updates**.
- Settings → Buttons can open Lembas with a double press of the side button.
- **The Lembas tile:** the Shire weekday and date, your next alarm if one is due within 12 hours (otherwise the mealtime), **when the look changes next** (*Starlit Night at 7:21 pm*), your favourites (then latest apps) and an **All apps** button.
- **Lembas complications for any watch face:** the **Shire date**, the **hobbit mealtime** and the **next Lembas look**. On another face: touch and hold → Edit → a complication → Lembas.
- **Wear OS 6:** to colour the watch's own menus and tiles from the face, set the watch's theme (in its Settings) to **match the watch face**.

## Building

**GitHub (no install needed):** every push runs `.github/workflows/build.yml`:
1. downloads the fonts (Google Fonts, SIL Open Font License),
2. renders the artwork and writes the watch face XML (`wear/tools/make_watchface.py`),
3. checks the XML against Google's Watch Face Format schema and validator,
4. builds both APKs, signed with the `LEMBAS_KEYSTORE_B64` / `LEMBAS_KEYSTORE_PASSWORD` secrets,
5. on `main`, publishes a release tagged `v<build>` with `lembas-wear.apk`, `lembas-watchface.apk` and `Lembas-watch-installer.zip` (the five newest are kept). Build numbers start at 2100, after the last watch build published from lembas-android (1400). On other branches it runs both on a Wear OS emulator instead and pushes screenshots of each look to the `screens` branch.

**Locally:** `python wear/tools/make_watchface.py watchface/src/main/res wear/src/main/res --preview out/` renders the face (it needs Playwright, Pillow and fontTools, and the fonts in `watchface/src/main/res/font/` under the names the workflow uses) and writes `out/faces.png`, a still of each look and the always-on display. Then open the folder in Android Studio and run `:wear` or `:watchface`.

## Project map

| Path | What it is |
|---|---|
| `watchface/` | The watch face: resources only, no code (Watch Face Format v2) |
| `wear/art/watch.html` | The four scenes in each season, their outlines for the always-on display, and the moving parts (flames, moon phases, weather), drawn in SVG |
| `wear/tools/make_watchface.py` | Renders the art, cuts fixed-weight fonts with lining figures, writes the watch face XML and the preview stills |
| `wear/tools/emulator-shots.sh` | Test builds: installs both on a Wear OS emulator and captures each look |
| `wear/src/.../MainActivity.kt` | The launcher app (Compose for Wear OS, Material 3) |
| `wear/src/.../LembasTile.kt` | The tile |
| `wear/src/.../WearLore.kt` | Looks, Shire calendar, Quenya hours, mealtimes, sun times |
| `wear/src/.../WearUpdater.kt` | Daily update check (while charging) and self-install |
| `wear/install/` | The Windows installer for the first install, and the one-off move from lembas-android |

## Credits

Fonts (SIL Open Font License): Cinzel by Natanael Gama; Cormorant Garamond by Christian Thalmann; IM Fell English by Igino Marini; Fraunces by Undercase Type; Alegreya Sans by Huerta Tipográfica.
Names and the Shire calendar come from J.R.R. Tolkien's legendarium. This is an unofficial fan project, not affiliated with the Tolkien Estate or any film studio.
