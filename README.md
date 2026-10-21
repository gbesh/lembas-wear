# Lembas for Wear OS — a Middle-earth watch face and launcher

*One small bite is enough.* The four Lembas looks, made for a round watch: a watch face that follows the sun, a launcher app in the look of the hour, and a tile.

Built and tested for the Pixel Watch (Wear OS 5 or later); it should work on any round Wear OS 5+ watch.

The phone launcher lives in **[gbesh/lembas-android](https://github.com/gbesh/lembas-android)** and the Windows version in **[gbesh/lembas-windows](https://github.com/gbesh/lembas-windows)**.

## Install (once)

You need a Windows PC on the same Wi-Fi as the watch.

1. Download **`Lembas-watch-installer.zip`** from the [latest release](https://github.com/gbesh/lembas-wear/releases/latest), unzip it and double-click **Install Lembas on your watch**.
2. On the watch, turn on Developer options: Settings → System → About → Versions, tap **Build number** 7 times.
3. In Settings → Developer options, turn on **ADB debugging** and **Wireless debugging**.
4. Follow the installer: on the watch, open Wireless debugging → **Pair new device** and type the address and code it shows, then the address from the main Wireless debugging screen. The installer puts the watch face and the app on the watch.
5. **Add the face:** touch and hold the watch face, swipe to the end, tap **+** and choose **Lembas**.
   **Add the tile:** swipe left from the face and add the **Lembas** tile.

You can turn Wireless debugging off again afterwards.

## Updates

The watch app keeps itself and the watch face up to date from this repo's latest release. It checks once a day, **only while the watch is charging**, so it costs nothing during the day. To update straight away, open Lembas and tap **Watch face & updates** at the bottom.

Every push to `main` builds a new release. Releases are signed with the same key as every earlier Lembas watch build (kept in the repo's Actions secrets, never in the code), so each one installs over the last.

**Installed before the move?** The watch builds used to be published in gbesh/lembas-android, and those builds still look there for updates. Run **`wear/install/Move from lembas-android (once).cmd`** on a Windows PC once: it removes the old watch app and watch face, installs the current ones from here, and from then on they update from this repo. Removing the old version takes the face and tile off the watch, so add them back afterwards (step 5 above).

## The watch face

A clean, modern face in the four Lembas palettes:

- **Large stacked numerals** (Fraunces): the hours heavy in the look's colour, the minutes light.
- **The sun ring**, a 24-hour ring around the rim with noon at the top and midnight at the bottom. By day the sun travels across its bright half, from sunrise on the left to sunset on the right; at night it's the moon, in tonight's real phase.
- **Wed 21** and the **Shire date** (e.g. *Hevensday · 30 Winterfilth*) above the time, and the **hobbit mealtime** below it (*Second breakfast*, *Afternoon tea*, … *The Shire sleeps*).
- **Two complications**, one either side of the time (battery and steps by default; touch and hold the face → Customise to change them).

| Look | When (Follow the sun) | Colours |
|---|---|---|
| **Shire Morning** | sunrise → midday | Deep green, lit with morning gold from above; golden hours |
| **Red Book** | midday → sunset | Oxblood, lit like a page by the fire; vermilion hours |
| **Starlit Night** | sunset → 11pm, 4am → sunrise | **Black** with a little blue at the zenith and a few twinkling stars; gold hours |
| **Elven Silver** | 11pm → 4am | **Black** with a breath of silver; silver-blue hours |

The night looks are true black, which costs almost nothing on an OLED screen. Day and night come from the watch's own weather data (6am–6pm if it has none), and the morning/afternoon switch is at solar midday. Touch and hold → Customise picks one look to keep instead, and has a **Southern hemisphere moon** switch.

**Always-on display:** the time in light grey numerals, the date and Shire date, and the four main ticks.

**Light on the battery:** very little moves (the sun's glow, the sun or moon along the ring, a few stars at night). The animation values change at most once a second and the watch glides between them at 8–12 frames per second. Everything stops in ambient mode.

## The watch app and tile

- **Lembas** (in the app list): in the same type and colours as the face: the date, the Shire date, the time (hours heavy, minutes light) and the mealtime, then **Lately** (your four latest apps) and **All apps** A–Z. Turn the crown to scroll; touch and hold an app for its info page. At the bottom: **Look** (follow the sun, or one look) and **Watch face & updates**.
- Settings → Buttons can open Lembas with a double press of the side button.
- **The Lembas tile:** the Shire weekday and date, the mealtime, your four latest apps and an **All apps** button.

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
| `wear/art/watch.html` | The backgrounds, the sun ring, the sun and the moon phases, drawn in SVG |
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
