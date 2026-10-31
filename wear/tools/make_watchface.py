"""Build the Lembas watch face (Watch Face Format) for round Wear OS watches.

Renders the backgrounds and sprites from wear/art/watch.html, makes fixed-weight copies of the
fonts, then writes watchface/src/main/res/raw/watchface.xml. Everything that moves is described
declaratively, so the watch's own renderer animates it (and stops in ambient mode); there is no
code on the watch.

The design: four flat, colourful little scenes that follow the sun (the Shire's round door, the
fire by the Red Book, mountains and a cabin under the stars, Rivendell's silver trees), each in
four seasons, with large stacked numerals over them (the hours heavy, the minutes light), the
date and the Shire date above, the hobbit mealtime below and a complication either side. Small
things move: the sun's glow and chimney smoke, the fire and its embers, twinkling stars, tonight's
real moon and the odd shooting star, Earendil's star and drifting motes; and, from the watch's own
weather, cloud, fog, rain or snow. The always-on display shows the scene as fine grey lines.

Usage: python make_watchface.py [watchface_res_dir] [wear_app_res_dir] [--preview out_dir]
"""
import asyncio
import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "wear" / "art" / "watch.html"
ARGS = [x for x in sys.argv[1:] if not x.startswith("--")]
PREVIEW = sys.argv[sys.argv.index("--preview") + 1] if "--preview" in sys.argv else None
if PREVIEW in ARGS:
    ARGS.remove(PREVIEW)
RES = Path(ARGS[0]) if ARGS else ROOT / "watchface" / "src" / "main" / "res"
S = 450  # the face's virtual canvas
C = S / 2

# part -> (width, height) of the rendered PNG; "x-outline" is scene x drawn as lines (always-on display)
SEASONS = ["spring", "summer", "autumn", "winter"]
BACKS = {   # look -> the picture for each season (the fire is the same all year; the lake only changes in winter)
    "shire": {se: f"shire-{se}" for se in SEASONS},
    "redbook": {se: "redbook" for se in SEASONS},
    "starlit": {se: "starlit-winter" if se == "winter" else "starlit-summer" for se in SEASONS},
    "elven": {se: f"elven-{se}" for se in SEASONS},
}
ALL_BACKS = {b for look in BACKS.values() for b in look.values()}
PARTS = {
    **{b: (450, 450) for look in BACKS.values() for b in look.values()},
    **{f"{k}-outline": (450, 450) for k in BACKS},
    "logs": (450, 450), "flame-outer": (120, 206), "flame-mid": (84, 130), "flame-inner": (40, 72),
    **{f"moon{i}": (64, 64) for i in range(8)}, "moonglow": (140, 140), "shooting": (100, 34),
    "elven-star": (80, 80), "sunglow": (220, 220), "dawnglow": (450, 450), "fox": (60, 34), "puff": (24, 24), "cloud": (150, 60), "fog": (600, 120),
    **{f"rain{i}": (450, 450) for i in range(8)}, **{f"snow{i}": (450, 450) for i in range(8)},
}

# Fixed-weight cuts of the variable fonts (renderers don't all honour weight on variable fonts),
# with lining figures baked in
STATIC_FONTS = {
    "numerals_heavy": ("fraunces.ttf", {"wght": 760, "opsz": 144, "SOFT": 50, "WONK": 0}),
    "numerals_light": ("fraunces.ttf", {"wght": 280, "opsz": 144, "SOFT": 50, "WONK": 0}),
    "lore_italic": ("fraunces_italic.ttf", {"wght": 420, "opsz": 24, "SOFT": 50, "WONK": 0}),
}


def res_name(part):
    return "wf_" + part.replace("-", "_")


async def render():
    from playwright.async_api import async_playwright
    out = RES / "drawable-nodpi"
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 450, "height": 450})
        for part, (w, h) in PARTS.items():
            await pg.set_viewport_size({"width": w, "height": h})
            src, outline = (BACKS[part[:-8]]["summer"], 1) if part.endswith("-outline") else (part, 0)
            await pg.goto(f"{ART.as_uri()}?part={src}&w={w}&h={h}&outline={outline}")
            await pg.wait_for_timeout(100)
            png = out / f"{res_name(part)}.png"
            await pg.screenshot(path=str(png), omit_background=True, clip={"x": 0, "y": 0, "width": w, "height": h})
            if part in ALL_BACKS:   # opaque pictures; the sprites keep their soft edges
                quantize(png)
        await b.close()


def quantize(png):
    """Flat art needs few colours: a 256-colour palette keeps the face small and quick to load."""
    from PIL import Image
    im = Image.open(png).convert("RGB")
    im.quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(png, optimize=True)


def make_static_fonts():
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont
    fonts = RES / "font"
    for name, (src, axes) in STATIC_FONTS.items():
        f = TTFont(fonts / src)
        axes = {k: v for k, v in axes.items() if k in {a.axisTag for a in f["fvar"].axes}}
        instantiateVariableFont(f, axes, inplace=True, updateFontNames=False)
        freeze(f, ("lnum", "pnum"))
        f.save(fonts / f"{name}.ttf")


def freeze(f, features):
    """Bake single substitutions (e.g. lining figures) into the character map, as the watch can't ask for them."""
    if "GSUB" not in f:
        return
    gsub = f["GSUB"].table
    swap = {}
    for rec in gsub.FeatureList.FeatureRecord:
        if rec.FeatureTag not in features:
            continue
        for li in rec.Feature.LookupListIndex:
            lk = gsub.LookupList.Lookup[li]
            for st in lk.SubTable:
                st = st.ExtSubTable if lk.LookupType == 7 else st
                if getattr(st, "mapping", None):
                    swap.update(st.mapping)
    for t in f["cmap"].tables:
        for cp, g in list(t.cmap.items()):
            if g in swap and chr(cp).isdigit():
                t.cmap[cp] = swap[g]


# ------------------------------------------------------------------ expressions
# Seconds today. Expressions only change once a second; each moving part carries an <Animation>
# so the watch itself glides between those values at a low frame rate. (Driving parts from
# SECOND_MILLISECOND makes the renderer evaluate everything on every frame, which is what lagged.)
T = "[SECONDS_IN_DAY]"


def phase(dur, off=0.0):
    return f"fract(({T} + {off:.2f}) / {dur})"


def wave(dur, off=0.0):  # 0..1..0, smoothly
    return f"(0.5 - 0.5 * cos(6.28319 * {phase(dur, off)}))"


def chain(cases, default):
    """Nested ternary: cases = [(condition, value), ...]."""
    e = default
    for cond, val in reversed(cases):
        e = f"({cond} ? {val} : {e})"
    return e


def q(s):
    return '"' + s + '"'


H = "[HOUR_0_23]"
WEEK = ["Sunday", "Monday", "Trewsday", "Hevensday", "Mersday", "Highday", "Sterday"]
MONTHS = ["Afteryule", "Solmath", "Rethe", "Astron", "Thrimidge", "Forelithe",
          "Afterlithe", "Wedmath", "Halimath", "Winterfilth", "Blotmath", "Foreyule"]
WD = chain([(f"[DAY_OF_WEEK] == {i + 1}", q(n)) for i, n in enumerate(WEEK[:-1])], q(WEEK[-1]))
WD_UP = chain([(f"[DAY_OF_WEEK] == {i + 1}", q(n.upper())) for i, n in enumerate(WEEK[:-1])], q(WEEK[-1].upper()))
MEAL = chain([(f"({H} == 5 || {H} == 6)", q("Kettle on")), (f"({H} == 7 || {H} == 8)", q("Breakfast")),
              (f"({H} == 9 || {H} == 10)", q("Second breakfast")), (f"{H} == 11", q("Elevenses")),
              (f"({H} == 12 || {H} == 13)", q("Luncheon")), (f"{H} == 14", q("A stroll in the garden")),
              (f"({H} == 15 || {H} == 16)", q("Afternoon tea")), (f"{H} == 17", q("A pint at the Dragon")),
              (f"({H} == 18 || {H} == 19)", q("Dinner")), (f"({H} == 20 || {H} == 21)", q("Supper"))],
             q("The Shire sleeps"))

# The Shire calendar: the year starts on 1 Yule, 21 December; twelve 30-day months, two Yule
# days, and three Lithe days (four in leap years) around Mid-year's Day.
LEAP = "((([YEAR] % 4 == 0) && ([YEAR] % 100 != 0)) || ([YEAR] % 400 == 0))"
E = "(([MONTH] == 12 && [DAY] >= 21) ? ([DAY] - 21) : ([DAY_OF_YEAR] + 10))"
K = f"({E} - 2)"
L = f"({LEAP} ? 4 : 3)"
K2 = f"({K} - 180 - {L})"


def month_name(idx, up=False):
    ms = [m.upper() for m in MONTHS] if up else MONTHS
    return chain([(f"{idx} == {i}", q(n)) for i, n in enumerate(ms[:-1])], q(ms[-1]))


def shire_name(up=False):
    u = (lambda s: s.upper()) if up else (lambda s: s)
    return chain([(f"{E} <= 1", q(u("Yule"))), (f"{K} < 180", month_name(f"floor({K} / 30)", up)),
                  (f"{K} < 180 + {L}", chain([(f"({K} - 180 == 0 || {K} - 180 == {L} - 1)", q(u("Lithe"))),
                                              (f"{K} - 180 == 1", q(u("Mid-year’s Day")))], q(u("Overlithe"))))],
                 month_name(f"(6 + floor({K2} / 30))", up))


SHIRE_DAY = chain([(f"{E} == 0", "1"), (f"{E} == 1", "2"), (f"{K} < 180", f"({K} % 30 + 1)"),
                   (f"{K} < 180 + {L}", f"(({K} - 180 == 0) ? 1 : (({K} - 180 == {L} - 1) ? 2 : {q('')}))")],
                  f"({K2} % 30 + 1)")
HOUR = "([IS_24_HOUR_MODE] ? [HOUR_0_23] : [HOUR_1_12])"

# ------------------------------------------------------------------ the sun, exactly as the phone and the watch app work it out
# The main city of each time zone (the same table as lembas-android's Sun.kt and the watch app's
# WearLore.kt), with the zone's standard UTC offset and its daylight-saving shift, in minutes.
CITIES = [
    ("Australia/Sydney", -33.87, 151.21, 600, 60),
    ("Australia/Melbourne", -37.81, 144.96, 600, 60),
    ("Australia/Brisbane", -27.47, 153.03, 600, 0),
    ("Australia/Adelaide", -34.93, 138.60, 570, 60),
    ("Australia/Perth", -31.95, 115.86, 480, 0),
    ("Australia/Hobart", -42.88, 147.33, 600, 60),
    ("Australia/Darwin", -12.46, 130.84, 570, 0),
    ("Australia/Canberra", -35.28, 149.13, 600, 60),
    ("Australia/Lord_Howe", -31.55, 159.08, 630, 30),
    ("Australia/Broken_Hill", -31.95, 141.45, 570, 60),
    ("Pacific/Auckland", -36.85, 174.76, 720, 60),
    ("Pacific/Fiji", -18.14, 178.44, 720, 0),
    ("Asia/Tokyo", 35.68, 139.69, 540, 0),
    ("Asia/Seoul", 37.57, 126.98, 540, 0),
    ("Asia/Shanghai", 31.23, 121.47, 480, 0),
    ("Asia/Hong_Kong", 22.32, 114.17, 480, 0),
    ("Asia/Singapore", 1.35, 103.82, 480, 0),
    ("Asia/Kolkata", 19.08, 72.88, 330, 0),
    ("Asia/Dubai", 25.20, 55.27, 240, 0),
    ("Asia/Jakarta", -6.21, 106.85, 420, 0),
    ("Asia/Manila", 14.60, 120.98, 480, 0),
    ("Asia/Bangkok", 13.76, 100.50, 420, 0),
    ("Europe/London", 51.51, -0.13, 0, 60),
    ("Europe/Dublin", 53.35, -6.26, 0, 60),
    ("Europe/Paris", 48.86, 2.35, 60, 60),
    ("Europe/Berlin", 52.52, 13.40, 60, 60),
    ("Europe/Madrid", 40.42, -3.70, 60, 60),
    ("Europe/Rome", 41.90, 12.50, 60, 60),
    ("Europe/Amsterdam", 52.37, 4.90, 60, 60),
    ("Europe/Stockholm", 59.33, 18.07, 60, 60),
    ("Europe/Athens", 37.98, 23.73, 120, 60),
    ("Europe/Moscow", 55.76, 37.62, 180, 0),
    ("Africa/Johannesburg", -26.20, 28.05, 120, 0),
    ("Africa/Cairo", 30.04, 31.24, 120, 60),
    ("Africa/Lagos", 6.52, 3.38, 60, 0),
    ("Africa/Nairobi", -1.29, 36.82, 180, 0),
    ("America/New_York", 40.71, -74.01, -300, 60),
    ("America/Chicago", 41.88, -87.63, -360, 60),
    ("America/Denver", 39.74, -104.99, -420, 60),
    ("America/Los_Angeles", 34.05, -118.24, -480, 60),
    ("America/Phoenix", 33.45, -112.07, -420, 0),
    ("America/Toronto", 43.65, -79.38, -300, 60),
    ("America/Vancouver", 49.28, -123.12, -480, 60),
    ("America/Mexico_City", 19.43, -99.13, -360, 0),
    ("America/Sao_Paulo", -23.55, -46.63, -180, 0),
    ("America/Argentina/Buenos_Aires", -34.60, -58.38, -180, 0),
    ("America/Santiago", -33.45, -70.67, -240, 60),
    ("America/Bogota", 4.71, -74.07, -300, 0),
    ("America/Lima", -12.05, -77.04, -300, 0),
    ("Pacific/Honolulu", 21.31, -157.86, -600, 0),
    ("America/Anchorage", 61.22, -149.90, -540, 60),
]


def by_zone(values, default):
    return chain([(f'[TIMEZONE_ID] == {q(z)}', v) for z, v in values], default)


LAT = by_zone([(z, f"{la}") for z, la, lo, std, dst in CITIES], "999")
LON = by_zone([(z, f"{lo}") for z, la, lo, std, dst in CITIES], "0")
OFF = by_zone([(z, f"([IS_DAYLIGHT_SAVING_TIME] ? {std + dst} : {std})" if dst else f"{std}") for z, la, lo, std, dst in CITIES], "0")
KNOWN = f"({LAT} < 900)"                      # a time zone in the table
G = "(0.0172142 * ([DAY_OF_YEAR] - 1))"         # 2pi/365 per day
EOT = f"(229.18 * (0.000075 + 0.001868 * cos({G}) - 0.032077 * sin({G}) - 0.014615 * cos(2 * {G}) - 0.040849 * sin(2 * {G})))"
DEC = (f"(0.006918 - 0.399912 * cos({G}) + 0.070257 * sin({G}) - 0.006758 * cos(2 * {G}) + 0.000907 * sin(2 * {G})"
       f" - 0.002697 * cos(3 * {G}) + 0.00148 * sin(3 * {G}))")
SUN_NOON = f"(720 - 4 * {LON} - {EOT} + {OFF})"
COS_HA = f"(cos(rad(90.833)) / (cos(rad({LAT})) * cos({DEC})) - tan(rad({LAT})) * tan({DEC}))"
HA = f"deg(acos(clamp({COS_HA}, -1, 1)))"
RISE = f"clamp(floor({SUN_NOON} - 4 * {HA}), 0, 1439)"
NOON = f"clamp(floor({SUN_NOON}), 0, 1439)"
SET = f"clamp(floor({SUN_NOON} + 4 * {HA}), 0, 1439)"
# Late afternoon: the sun down to 15 degrees (the fireside Red Book look takes over). Always before
# sunset; 0 hour angle (noon) if the sun never climbs that high.
COS_HE = f"((sin(rad(15)) - sin(rad({LAT})) * sin({DEC})) / (cos(rad({LAT})) * cos({DEC})))"
HE = f"deg(acos(clamp({COS_HE}, -1, 1)))"
EVENING = f"clamp(floor({SUN_NOON} + 4 * {HE}), 0, 1439)"
MINS = "([HOUR_0_23] * 60 + [MINUTE])"

# Day and night: from the sun for the zone's main city; for a zone not in the table, from the
# watch's weather (or 6am-6pm without it), with midday at 12:00 (1pm in daylight saving).
WEATHER_DAY = "([WEATHER.IS_AVAILABLE] ? ([WEATHER.IS_DAY] ? 1 : 0) : (([HOUR_0_23] >= 6 && [HOUR_0_23] < 18) ? 1 : 0))"
WEATHER_EVENING = "1020"   # 5pm
IS_DAY = f"({KNOWN} ? (({MINS} >= {RISE} && {MINS} < {SET}) ? 1 : 0) : {WEATHER_DAY})"
# The phone's schedule, in the same order: sunrise to late afternoon Shire, late afternoon to
# sunset Red Book, 11pm to 4am Elven, otherwise Starlit.
LOOK_EXPR = {
    "shire": f"({KNOWN} ? ({MINS} >= {RISE} && {MINS} < {EVENING}) : ({WEATHER_DAY} == 1 && {MINS} < {WEATHER_EVENING}))",
    "redbook": f"({KNOWN} ? ({MINS} >= {EVENING} && {MINS} < {SET}) : ({WEATHER_DAY} == 1 && {MINS} >= {WEATHER_EVENING}))",
    "elven": f"({MINS} >= 1380 || {MINS} < 240)",
}


HOUR_Z = "([IS_24_HOUR_MODE] ? [HOUR_0_23_Z] : [HOUR_1_12_Z])"

# ------------------------------------------------------------------ layout
NUM_SIZE = 112
# where the words sit: the time high on the face over the scene (Rivendell's lower, under the trees' crowns)
LAYOUT = {
    "top": dict(date=(55, 44, 340, 28), hours=(75, 62, 300, 106), mins=(75, 152, 300, 106), meal=(95, 258, 260, 30)),
    "low": dict(date=(55, 92, 340, 26), hours=(75, 110, 300, 106), mins=(75, 200, 300, 106), meal=(95, 296, 260, 30)),
}
COMP_D = 62
COMPS = [(0, 37, 169, "WATCH_BATTERY", "Left"), (1, 351, 169, "STEP_COUNT", "Right")]
COMP_TEXT = "#FFF4F4F4"

# Each look's type colours (hours, minutes, date line, mealtime) and the complication discs.
STYLE = {
    "shire": dict(layout="top", hours="#FF24452A", mins="#FF3F6B3A", lore="#FF55703F", meal="#FFE7DFC8", pill="#FF24452A",
                  plate="#E624452A"),
    "redbook": dict(layout="top", hours="#FFF1E9DA", mins="#FFF2B48A", lore="#FFF2B48A", meal="#FFF1E9DA", pill=None,
                    plate="#40FBEBD0"),
    "starlit": dict(layout="top", hours="#FFDAC696", mins="#FFECE6D8", lore="#FFB9AEE0", meal="#FFDAC696", pill=None,
                    plate="#2EF4EAD0"),
    "elven": dict(layout="low", hours="#FFE6F4F6", mins="#FF7FC8CC", lore="#FF7FC8CC", meal="#FFC9D8DC", pill=None,
                  plate="#B305090B"),
}
AMBIENT = dict(hours="#FFB0B0B0", mins="#FFB0B0B0", lore="#FF8A8A8A", meal="#FF8A8A8A")

# Seasons by the month, flipped south of the equator (from the time zone's main city).
NORTH_SEASON = "(([MONTH] == 12 || [MONTH] <= 2) ? 3 : (([MONTH] <= 5) ? 0 : (([MONTH] <= 8) ? 1 : 2)))"
SOUTH = f"({KNOWN} && {LAT} < 0)"
SEASON = f"({SOUTH} ? (({NORTH_SEASON} + 2) % 4) : {NORTH_SEASON})"

# The watch's own weather (Wear OS 5): its conditions folded into the few the scenes draw.
WX = "[WEATHER.CONDITION]"
WEATHER = {
    "cloudy": f"({WX} == 2)",
    "fog": f"({WX} == 3 || {WX} == 13)",
    "rain": f"({WX} == 4 || {WX} == 6 || {WX} == 9 || {WX} == 10 || {WX} == 12)",
    "snow": f"({WX} == 5 || {WX} == 7 || {WX} == 11)",
}


# ------------------------------------------------------------------ XML helpers
def a(v):
    return escape(str(v), {'"': "&quot;"})


def tr(target, value):
    return f'<Transform target="{target}" value="{a(value)}"/>'


def glide(target, value, fps=12, interp="LINEAR", dur=1):
    """A transform the watch animates smoothly whenever its value changes."""
    return (f'<Transform target="{target}" value="{a(value)}"><Animation duration="{dur}" interpolation="{interp}" '
            f'fps="{fps}" repeat="0"/></Transform>')


AMBIENT_OFF = '<Variant mode="AMBIENT" target="alpha" value="0"/>'


def image(name, x, y, w, h, transforms="", extra="", px=0.5, py=0.5):
    return (f'<PartImage x="{round(x)}" y="{round(y)}" width="{w}" height="{h}" pivotX="{px}" pivotY="{py}"{extra}>'
            f'{transforms}<Image resource="{res_name(name)}"/></PartImage>')


def dot(x, y, r, color, transforms=""):
    s = math.ceil(r * 2 + 2)
    pad = (s - r * 2) / 2
    return (f'<PartDraw x="{round(x - s / 2)}" y="{round(y - s / 2)}" width="{s}" height="{s}" pivotX="0.5" pivotY="0.5">{transforms}'
            f'<Ellipse x="{pad:.2f}" y="{pad:.2f}" width="{r * 2:.2f}" height="{r * 2:.2f}"><Fill color="{color}"/></Ellipse></PartDraw>')


def font(family, size, color, template, params, slant="NORMAL", spacing=None):
    sp = f' letterSpacing="{spacing}"' if spacing is not None else ""
    ps = "".join(f'<Parameter expression="{a(p)}"/>' for p in params)
    return (f'<Font family="{family}" size="{size}" color="{color}" slant="{slant}" weight="NORMAL"{sp}>'
            f'<Template>{a(template)}{ps}</Template></Font>')


APP = "com.middleearth.launcher/com.middleearth.lembas.wear.MainActivity"   # the Lembas watch app


def text(box, family, size, color, template, params, slant="NORMAL", spacing=None, launch=None):
    x, y, w, h = box
    tap = f'<Launch target="{launch}"/>' if launch else ""
    return (f'<PartText x="{x}" y="{y}" width="{w}" height="{h}">{tap}<Text align="CENTER" ellipsis="TRUE">'
            f'{font(family, size, color, template, params, slant, spacing)}</Text></PartText>')


def group(name, body, extra=""):
    return f'<Group name="{name}" x="0" y="0" width="{S}" height="{S}"{extra}>{body}</Group>'


def disc(cx, cy, d, fill):
    s = math.ceil(d + 2)
    o = (s - d) / 2
    return (f'<PartDraw x="{round(cx - s / 2)}" y="{round(cy - s / 2)}" width="{s}" height="{s}">'
            f'<Ellipse x="{o:.2f}" y="{o:.2f}" width="{d:.2f}" height="{d:.2f}"><Fill color="{fill}"/></Ellipse></PartDraw>')


def pill(x, y, w, h, fill):
    return (f'<PartDraw x="{x}" y="{y}" width="{w}" height="{h}"><RoundRectangle x="0" y="0" width="{w}" height="{h}" '
            f'cornerRadiusX="{h / 2:g}" cornerRadiusY="{h / 2:g}"><Fill color="{fill}"/></RoundRectangle></PartDraw>')


def condition(cases, default=""):
    """cases: [(name, expression, body)] -> a Condition showing the first that's true."""
    exprs = "".join(f'<Expression name="{n}"><![CDATA[{e}]]></Expression>' for n, e, _ in cases)
    comps = "".join(f'<Compare expression="{n}">{b}</Compare>' for n, _, b in cases)
    return f'<Condition><Expressions>{exprs}</Expressions>{comps}' + (f'<Default>{default}</Default>' if default else '') + '</Condition>'


def fade(p):   # 0 at both ends of a loop, so a part can jump back to its start unseen
    return f"(0.5 - 0.5 * cos(6.28319 * {p}))"


# ------------------------------------------------------------------ the moving parts
def backdrop(look):
    """The season's picture (four pictures, chosen by the month)."""
    names = BACKS[look]
    if len(set(names.values())) == 1:
        return image(names["summer"], 0, 0, S, S)
    cases = [(f"{look}_s{i}", f"{SEASON} == {i}", image(names[se], 0, 0, S, S)) for i, se in enumerate(SEASONS[:-1])]
    return condition(cases, image(names["winter"], 0, 0, S, S))


def twinkles(seed, spots):
    rnd = random.Random(seed)
    return "".join(dot(x, y, rnd.uniform(1.1, 1.8), "#FFF1F0EB", glide("alpha", f"40 + 215 * {wave(rnd.randint(4, 8), rnd.randint(0, 7))}", fps=8))
                   for x, y in spots)


def dawn_dusk():
    """For the twenty minutes either side of sunrise and sunset, a pink and amber wash from the horizon."""
    near = f"min(abs({MINS} - {RISE}), abs({MINS} - {SET}))"
    return image("dawnglow", 0, 0, S, S, glide("alpha", f"({KNOWN} && {near} < 20) ? 200 * (1 - {near} / 20) : 0", fps=4, dur=2))


def fox():
    """Now and then (for a minute, eight times a day) a fox trots across the Shire's hills."""
    window = "fract([SECONDS_IN_DAY] / 10800) * 180"   # minutes into each three-hour stretch
    p = f"(({window}) < 1 ? fract([SECONDS_IN_DAY] / 60) : 0)"
    return image("fox", 0, 0, 60, 34, glide("x", f"-70 + 560 * {p}") + glide("y", f"350 - 26 * sin(3.14 * {p})")
                 + glide("alpha", f"({window}) < 1 ? 255 : 0"))


def shire_motion():
    out = image("sunglow", 96 - 110, 300 - 110, 220, 220, glide("alpha", f"90 + 120 * {wave(7)}", fps=8)
                + glide("scaleX", f"0.94 + 0.1 * {wave(7)}", fps=8) + glide("scaleY", f"0.94 + 0.1 * {wave(7)}", fps=8))
    for k in range(3):   # chimney smoke: puffs rise, drift and fade
        p = phase(6, k * 2)
        out += image("puff", 0, 0, 24, 24, glide("x", f"346 + 22 * {p}") + glide("y", f"300 - 74 * {p}")
                     + glide("scaleX", f"0.5 + 0.9 * {p}") + glide("scaleY", f"0.5 + 0.9 * {p}") + glide("alpha", f"190 * {fade(p)}"))
    return out + fox()


def redbook_motion():
    out = ""
    for name, x, y, w, h, dur in (("flame-outer", 165, 244, 120, 206, 2.6), ("flame-mid", 183, 314, 84, 130, 1.9), ("flame-inner", 205, 364, 40, 72, 1.3)):
        out += image(name, x, y, w, h, glide("scaleY", f"0.9 + 0.16 * {wave(dur)}", fps=12, interp="EASE_IN_OUT")
                     + glide("scaleX", f"1.04 - 0.08 * {wave(dur, dur / 3)}", fps=12, interp="EASE_IN_OUT"), px=0.5, py=1.0)
    out += image("logs", 0, 0, S, S)
    rnd = random.Random(5)
    for k in range(7):   # embers
        p = phase(rnd.uniform(3, 5), rnd.uniform(0, 5))
        x0 = rnd.uniform(195, 255)
        out += dot(0, 0, rnd.uniform(1.6, 2.6), "#FFFFC56A", glide("x", f"{x0:.0f} + 24 * sin(6.28 * {p})") + glide("y", f"300 - 90 * {p}")
                   + glide("alpha", f"230 * {fade(p)}"))
    return out


def moon_phase():
    """Tonight's moon, in its real phase (mirrored for the southern hemisphere)."""
    idx = "(floor(([MOON_PHASE_POSITION] + 1.75) / 3.5) % 8)"
    # the full moon a little larger
    img = lambda i, flip: image(f"moon{i}", 118 - 32, 233 - 32, 64, 64, (tr("scaleX", "1.2") + tr("scaleY", "1.2")) if i == 4 else "",
                                extra=' scaleX="-1"' if flip else "")
    def pick(flip):
        return condition([(f"m{i}{'s' if flip else 'n'}", f"{idx} == {i}", img(i, flip)) for i in range(1, 8)], img(0, flip))
    return condition([("south_moon", SOUTH, pick(True))], pick(False))


def starlit_motion():
    out = image("moonglow", 118 - 70, 233 - 70, 140, 140, glide("alpha", f"150 + 105 * {wave(8)}", fps=8))
    out += moon_phase()
    out += twinkles(7, [(40, 60), (150, 30), (300, 36), (420, 110), (24, 160), (402, 196), (180, 300), (270, 286)])
    # a shooting star now and then; every few seconds on meteor-shower nights (the Perseids in
    # mid-August, the Geminids in mid-December)
    meteors = "(([MONTH] == 8 && [DAY] >= 11 && [DAY] <= 13) || ([MONTH] == 12 && [DAY] >= 13 && [DAY] <= 15))"
    p = f"({meteors} ? fract(([SECONDS_IN_DAY] + 3) / 7) : {phase(29, 3)})"
    out += image("shooting", 0, 0, 100, 34, glide("x", f"250 + 110 * {p}") + glide("y", f"18 + 34 * {p}")
                 + glide("alpha", f"(({p}) < 0.1) ? 255 * sin(31.4 * ({p})) : 0", fps=15))
    return out


def elven_motion():
    out = image("elven-star", 225 - 40, 50 - 40, 80, 80, glide("alpha", f"150 + 105 * {wave(5)}", fps=8)
                + glide("scaleX", f"0.85 + 0.22 * {wave(5)}", fps=8) + glide("scaleY", f"0.85 + 0.22 * {wave(5)}", fps=8))
    out += twinkles(8, [(118, 40), (334, 44), (60, 70), (392, 76), (170, 20), (290, 18)])
    rnd = random.Random(9)
    for k in range(8):   # motes of light drifting up from the knoll
        p = phase(rnd.uniform(9, 15), rnd.uniform(0, 14))
        x0 = rnd.uniform(120, 330)
        out += dot(0, 0, rnd.uniform(1.6, 2.4), "#FFDCEBF0", glide("x", f"{x0:.0f} + 12 * sin(6.28 * {p})") + glide("y", f"430 - 130 * {p}")
                   + glide("alpha", f"200 * {fade(p)}"))
    return out


MOTION = {"shire": shire_motion, "redbook": redbook_motion, "starlit": starlit_motion, "elven": elven_motion}


def weather(look):
    """Cloud, fog, rain or snow from the watch's weather; never indoors by the fire."""
    if look == "redbook":
        return ""
    light = look == "shire"
    cloud_alpha = 235 if light else 120
    clouds = "".join(image("cloud", 0, y, 150, 60, glide("x", f"-160 + 610 * ({WX} == 15 ? {phase(dur / 6, off)} : {phase(dur, off)})") + tr("alpha", str(cloud_alpha))
                                  + tr("scaleX", str(sc)) + tr("scaleY", str(sc)), extra='' if light else ' tintColor="#FF8A90B8"')
                     for y, dur, off, sc in ((14, 90, 0, 1.3), (52, 120, 50, 1.0), (300, 150, 100, 1.2)))
    fog = "".join(image("fog", 0, y, 600, 120, glide("x", f"-150 + 100 * {wave(60, off)}") + tr("alpha", "255"))
                  for y, off in ((250, 0), (330, 30)))
    loop = lambda kind: (f'<PartAnimatedImage x="0" y="0" width="{S}" height="{S}">'
                         f'<AnimationController play="ON_VISIBLE" repeat="TRUE" loopCount="0" resumePlayBack="TRUE" beforePlaying="FIRST_FRAME" afterPlaying="FIRST_FRAME"/>'
                         f'<SequenceImages loopCount="0" frameRate="10">' + "".join(f'<Image resource="{res_name(f"{kind}{i}")}"/>' for i in range(8))
                         + '</SequenceImages></PartAnimatedImage>')
    cases = [(f"{look}_cloudy", f"{WEATHER['cloudy']} || {WX} == 15", clouds), (f"{look}_fog", WEATHER["fog"], fog),
             (f"{look}_rain", WEATHER["rain"], loop("rain")), (f"{look}_snow", WEATHER["snow"], loop("snow"))]
    return condition([(f"{look}_wx", "[WEATHER.IS_AVAILABLE]", condition(cases))])


def words(st, ambient=False):
    """Tap the date for the calendar, the time for alarms, the Shire date or mealtime for Lembas."""
    lay = LAYOUT[st["layout"]] if not ambient else LAYOUT["top"]
    tap = (lambda t: None) if ambient else (lambda t: t)
    out = text(lay["date"], "alegreya_sans", 20, st["lore"], "%s %s  ·  %s %s",
               ["[DAY_OF_WEEK_S]", "[DAY]", SHIRE_DAY, shire_name()], spacing=0.02, launch=tap(APP))
    out += text(lay["hours"], "numerals_light" if ambient else "numerals_heavy", NUM_SIZE, st["hours"], "%s", [HOUR_Z], launch=tap("ALARM"))
    out += text(lay["mins"], "numerals_light", NUM_SIZE, st["mins"], "%s", ["[MINUTE_Z]"], launch=tap("ALARM"))
    if not ambient:
        x, y, w, h = lay["meal"]
        if st.get("pill"):
            out += pill(x + 30, y, w - 60, h, st["pill"])
        out += text(lay["meal"], "lore_italic", 21, st["meal"], "%s", [MEAL], slant="ITALIC", launch=APP)
    return out


def look_group(look):
    st = STYLE[look]
    scene = backdrop(look) + MOTION[look]() + weather(look) + (dawn_dusk() if look in ("shire", "starlit") else "")
    scene += "".join(disc(x + COMP_D / 2, y + COMP_D / 2, COMP_D, st["plate"]) for _, x, y, _, _ in COMPS)
    return group(look, group(f"{look}-scene", AMBIENT_OFF + scene) + group(f"{look}-text", AMBIENT_OFF + words(st))
                 + group(f"{look}-ambient", f'<Variant mode="AMBIENT" target="alpha" value="255"/>' + ambient(look), extra=' alpha="0"'))


def ambient(look):
    """The always-on display: the scene as fine grey lines, thin numerals; it all drifts a few pixels each minute."""
    shift = (f'<Transform target="x" value="{a("3 * sin(rad([MINUTE] * 47))")}"/>'
             f'<Transform target="y" value="{a("3 * cos(rad([MINUTE] * 61))")}"/>')
    art = image(f"{look}-outline", 0, 0, S, S, extra=' alpha="150"')
    return group(f"{look}-ambient-drift", shift + art + words(AMBIENT, ambient=True))


def complication(slot, x, y, provider, label):
    d = COMP_D
    icon = lambda ix, iy, s: (f'<PartImage x="{ix}" y="{iy}" width="{s}" height="{s}" tintColor="{COMP_TEXT}">'
                              f'<Image resource="[COMPLICATION.MONOCHROMATIC_IMAGE]"/></PartImage>')
    short = icon(21, 8, 20) + text((3, 28, d - 6, 26), "alegreya_sans", 21, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"])
    frac = "clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN]) / ([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN]), 0, 1)"
    arc = lambda color, extra: (f'<PartDraw x="0" y="0" width="{d}" height="{d}"><Arc centerX="{d / 2:g}" centerY="{d / 2:g}" width="{d - 6}" height="{d - 6}" startAngle="0" endAngle="360">'
                                f'{extra}<Stroke color="{color}" thickness="3.5" cap="ROUND"/></Arc></PartDraw>')
    ranged = (arc("#33FFFFFF", "") + arc(COMP_TEXT, tr("endAngle", f"360 * {frac}"))
              + icon(22, 10, 18) + text((7, 27, d - 14, 24), "alegreya_sans", 19, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"]))
    return (f'<ComplicationSlot slotId="{slot}" name="slot{slot}" displayName="{label}" x="{x}" y="{y}" width="{d}" height="{d}" '
            f'supportedTypes="SHORT_TEXT RANGED_VALUE EMPTY" isCustomizable="TRUE">'
            f'<DefaultProviderPolicy defaultSystemProvider="{provider}" defaultSystemProviderType="SHORT_TEXT"/>'
            f'<BoundingOval x="0" y="0" width="{d}" height="{d}"/>'
            f'<Complication type="SHORT_TEXT">{short}</Complication><Complication type="RANGED_VALUE">{ranged}</Complication>'
            f'<Complication type="EMPTY"/></ComplicationSlot>')


def watchface_xml():
    auto_exprs = "".join(f'<Expression name="{k}"><![CDATA[{v}]]></Expression>' for k, v in LOOK_EXPR.items())
    auto = (f'<Condition><Expressions>{auto_exprs}</Expressions>'
            + "".join(f'<Compare expression="{k}">{look_group(k)}</Compare>' for k in LOOK_EXPR)
            + f'<Default>{look_group("starlit")}</Default></Condition>')
    options = f'<ListOption id="auto">{group("auto", auto)}</ListOption>'
    for k in ("shire", "redbook", "starlit", "elven"):
        options += f'<ListOption id="{k}">{look_group(k)}</ListOption>'
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<WatchFace width="{S}" height="{S}" clipShape="CIRCLE">'
            '<Metadata key="CLOCK_TYPE" value="DIGITAL"/><Metadata key="PREVIEW_TIME" value="10:08:32"/>'
            '<UserConfigurations>'
            '<ListConfiguration id="look" displayName="Look" defaultValue="auto">'
            '<ListOption id="auto" displayName="Follow the sun"/><ListOption id="shire" displayName="Shire Morning"/>'
            '<ListOption id="redbook" displayName="Red Book"/><ListOption id="starlit" displayName="Starlit Night"/>'
            '<ListOption id="elven" displayName="Elven Silver"/></ListConfiguration>'
            '</UserConfigurations>'
            '<Scene backgroundColor="#FF000000">'
            f'<ListConfiguration id="look">{options}</ListConfiguration>'
            + "".join(complication(*c) for c in COMPS)
            + '</Scene></WatchFace>\n')


# ------------------------------------------------------------------ still pictures (picker preview, app backgrounds, checks)
SAMPLE = {   # look: (hours, minutes, date line, meal, complications)
    "shire": ("09", "21", "Sat 31  ·  10 Blotmath", "Second breakfast", ("80%", "4,512")),
    "redbook": ("03", "30", "Sat 31  ·  10 Blotmath", "Afternoon tea", ("64%", "9,870")),
    "starlit": ("08", "05", "Sat 31  ·  10 Blotmath", "Supper", ("41%", "11,204")),
    "elven": ("01", "30", "Sat 31  ·  10 Blotmath", "The Shire sleeps", ("23%", "12,640")),
}


def still(look, with_words=True, ambient_mode=False, season="summer"):
    from PIL import Image, ImageDraw, ImageFont
    src = RES / "drawable-nodpi"
    fonts = RES / "font"
    hexc = lambda c: (int(c[3:5], 16), int(c[5:7], 16), int(c[7:9], 16), int(c[1:3], 16))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    load = lambda n: Image.open(src / f"{res_name(n)}.png").convert("RGBA")
    put = lambda n, x, y: img.alpha_composite(load(n), (int(x), int(y)))
    st = AMBIENT if ambient_mode else STYLE[look]
    if ambient_mode:
        o = load(f"{look}-outline")
        o.putalpha(o.getchannel("A").point(lambda v: v * 150 // 255))
        img.alpha_composite(o)
    else:
        img.alpha_composite(load(BACKS[look][season]))
        if look == "shire":
            put("sunglow", 96 - 110, 300 - 110)
            for k in range(3):
                put("puff", 346 + 8 * k, 300 - 26 * k)
        if look == "redbook":
            put("flame-outer", 165, 244); put("flame-mid", 183, 314); put("flame-inner", 205, 364); put("logs", 0, 0)
        if look == "starlit":
            put("moonglow", 118 - 70, 233 - 70); put("moon2", 118 - 32, 233 - 32)
        if look == "elven":
            put("elven-star", 225 - 40, 50 - 40)
    if not with_words:
        return img
    dr = ImageDraw.Draw(img)
    hh, mm, date, meal, comps = SAMPLE[look]
    lay = LAYOUT["top" if ambient_mode else st["layout"]]

    def box_text(box, fam, size, col, s):
        x, y, w, h = box
        f = ImageFont.truetype(str(fonts / f"{fam}.ttf"), size)
        asc, desc = f.getmetrics()
        dr.text((x + (w - f.getlength(s)) / 2, y + (h - (asc + desc)) / 2), s, font=f, fill=hexc(col))

    box_text(lay["date"], "alegreya_sans", 20, st["lore"], date)
    box_text(lay["hours"], "numerals_light" if ambient_mode else "numerals_heavy", NUM_SIZE, st["hours"], hh)
    box_text(lay["mins"], "numerals_light", NUM_SIZE, st["mins"], mm)
    if not ambient_mode:
        x, y, w, h = lay["meal"]
        if st.get("pill"):
            dr.rounded_rectangle((x + 30, y, x + w - 30, y + h), radius=h / 2, fill=hexc(st["pill"]))
        box_text(lay["meal"], "lore_italic", 21, st["meal"], meal)
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        for _, x, y, _, _ in COMPS:
            ImageDraw.Draw(layer).ellipse((x, y, x + COMP_D, y + COMP_D), fill=hexc(st["plate"]))
        img.alpha_composite(layer)
        dr = ImageDraw.Draw(img)
        for (_, x, y, _, _), v in zip(COMPS, comps):
            dr.ellipse((x + 25, y + 10, x + 37, y + 24), outline=hexc(COMP_TEXT), width=2)
            box_text((x + 3, y + 28, COMP_D - 6, 26), "alegreya_sans", 21, COMP_TEXT, v)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, S - 1, S - 1), fill=255)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    out.paste(img, (0, 0), mask)
    return out


def write_stills(wear_res):
    from PIL import Image
    nodpi = RES / "drawable-nodpi"
    still("starlit").convert("RGB").save(nodpi / "wf_preview.png", optimize=True)
    if wear_res:
        out = Path(wear_res) / "drawable-nodpi"
        out.mkdir(parents=True, exist_ok=True)
        for look in STYLE:   # the watch app's backgrounds and the tile's: the look's scene, without the words
            still(look, with_words=False).convert("RGB").save(out / f"wl_{look}.png", optimize=True)
        Image.open(nodpi / "wf_preview.png").save(out / "tile_preview.png")
    if PREVIEW:
        p = Path(PREVIEW)
        p.mkdir(parents=True, exist_ok=True)
        rows = [[still(k) for k in STYLE], [still(k, ambient_mode=True) for k in STYLE],
                [still("shire", season=se) for se in SEASONS], [still("elven", season=se) for se in SEASONS]]
        sheet = Image.new("RGB", (S * 4 + 35, S * 4 + 35), (40, 40, 40))
        for r, row in enumerate(rows):
            for i, im in enumerate(row):
                sheet.paste(im.convert("RGB"), (7 + i * (S + 7), 7 + r * (S + 7)))
        sheet.save(p / "faces.png")


async def main():
    await render()
    make_static_fonts()
    if len(ARGS) > 1:   # the watch app uses the same type as the face
        import shutil
        app_fonts = Path(ARGS[1]) / "font"
        app_fonts.mkdir(parents=True, exist_ok=True)
        for name in STATIC_FONTS:
            shutil.copy(RES / "font" / f"{name}.ttf", app_fonts / f"{name}.ttf")
    write_stills(ARGS[1] if len(ARGS) > 1 else None)
    raw = RES / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    xml = watchface_xml()
    (raw / "watchface.xml").write_text(xml, encoding="utf-8")
    print(f"watchface.xml: {len(xml) // 1024} KB, {len(PARTS)} images")


if __name__ == "__main__":
    asyncio.run(main())
