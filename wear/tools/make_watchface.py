"""Build the Lembas watch face (Watch Face Format) for round Wear OS watches.

Renders the still layers and sprites from wear/art/watch.html, makes fixed-weight copies of the
fonts, then writes watchface/src/main/res/raw/watchface.xml. Everything that moves is described
declaratively, so the watch's own renderer animates it (and stops in ambient mode); there is no
code on the watch.

Layout (450 x 450, round): the Shire date curves around the top, then the day and date, a large
time, the hobbit mealtime, and two large complications that sit low on the face like round doors.
The night looks are black, which costs next to nothing on an OLED screen.

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

# part -> (width, height) of the rendered PNG
PARTS = {
    "starlit-back": (450, 450), "moonglow": (90, 90), **{f"moon{i}": (44, 44) for i in range(8)},
    "shire-back": (450, 450), "rays": (130, 130), "sun": (120, 120), "cloud-a": (100, 40), "cloud-b": (70, 28),
    "redbook-back": (450, 450), "warmglow": (300, 220),
    "elven-back": (450, 450), "halo": (80, 80), "glint": (24, 24), "glyph": (32, 32),
}

# Fixed-weight cuts of the variable fonts (renderers don't all honour weight on variable fonts)
STATIC_FONTS = {
    "fraunces_display": ("fraunces.ttf", {"wght": 620, "opsz": 144, "SOFT": 0, "WONK": 0}),
    "fraunces_text": ("fraunces_italic.ttf", {"wght": 600, "opsz": 36, "SOFT": 0, "WONK": 0}),
    "cormorant_display": ("cormorant.ttf", {"wght": 620}),
    "cormorant_text": ("cormorant_italic.ttf", {"wght": 650}),
    "cinzel_label": ("cinzel.ttf", {"wght": 700}),
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
            await pg.goto(f"{ART.as_uri()}?part={part}&w={w}&h={h}")
            await pg.wait_for_timeout(100)
            await pg.screenshot(path=str(out / f"{res_name(part)}.png"), omit_background=True,
                                clip={"x": 0, "y": 0, "width": w, "height": h})
        await b.close()


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

# Which look: day (from the watch's weather, or 6am-6pm without it) before or after midday, and night
IS_DAY = "([WEATHER.IS_AVAILABLE] ? ([WEATHER.IS_DAY] ? 1 : 0) : (([HOUR_0_23] >= 6 && [HOUR_0_23] < 18) ? 1 : 0))"
MINS = "([HOUR_0_23] * 60 + [MINUTE])"
NOON = "(720 + ([IS_DAYLIGHT_SAVING_TIME] ? 60 : 0))"
LOOK_EXPR = {
    "shire": f"{IS_DAY} == 1 && {MINS} < {NOON}",
    "redbook": f"{IS_DAY} == 1 && {MINS} >= {NOON}",
    "elven": f"{IS_DAY} == 0 && ([HOUR_0_23] >= 23 || [HOUR_0_23] < 4)",
}


# ------------------------------------------------------------------ layout
ARC_R = 190                      # the curved Shire date, around the top
DATE_BOX = (80, 84, 290, 32)
TIME_BOX = (10, 106, 430, 168)
MEAL_BOX = (50, 268, 350, 38)
COMP_D = 100
COMPS = [(0, 113, 306, "WATCH_BATTERY", "Left"), (1, 237, 306, "STEP_COUNT", "Right")]

STYLE = {
    # fonts: arc, date, time, meal;  colours: arc, date, time, meal;  plate fill, plate ring
    "shire": dict(fonts=("alegreya_sans", "alegreya_sans", "fraunces_display", "fraunces_text"),
                  sizes=(21, 24, 150, 28), spacing=(0.12, 0.04),
                  colors=("#FF3E5A2E", "#FF3E5A2E", "#FF22391F", "#FF22391F"),
                  plate=("#FF2E5E3A", "#FFC9B48A", 4.0), upper_arc=True),
    "redbook": dict(fonts=("fell_sc", "fell_sc", "fell", "fell_italic"),
                    sizes=(23, 25, 150, 29), spacing=(0.06, 0.03),
                    colors=("#FF8E2416", "#FF4E3A22", "#FF22170D", "#FF8E2416"),
                    plate=("#FF8A2A1C", "#FF5E180F", 3.0), upper_arc=False),
    "starlit": dict(fonts=("cinzel_label", "cinzel_label", "cormorant_display", "cormorant_text"),
                    sizes=(19, 20, 160, 29), spacing=(0.1, 0.14),
                    colors=("#FFE6C987", "#FFD2CAB6", "#FFFAF3E2", "#FFE6C987"),
                    plate=("#FF000000", "#FF4A5578", 2.0), upper_arc=True),
    "elven": dict(fonts=("cinzel_label", "cinzel_label", "cormorant_display", "cormorant_text"),
                  sizes=(19, 20, 160, 29), spacing=(0.1, 0.14),
                  colors=("#FFBCCAD0", "#FFA3AFB5", "#FFF2F6F7", "#FFBFD7E3"),
                  plate=("#FF000000", "#FF6A777E", 1.6), upper_arc=True),
}
AMBIENT = dict(fonts=("cinzel_label", "cinzel_label", "cormorant_display", "cormorant_text"),
               sizes=(19, 20, 160, 29), spacing=(0.1, 0.14),
               colors=("#FF9A9A9A", "#FF808080", "#FFD8D8D8", "#FF9A9A9A"))
COMP_TEXT = "#FFF6EEDC"
COMP_ACCENT = "#FFE2B65A"


# ------------------------------------------------------------------ XML helpers
def a(v):
    return escape(str(v), {'"': "&quot;"})


def tr(target, value):
    return f'<Transform target="{target}" value="{a(value)}"/>'


def glide(target, value, fps=12, interp="LINEAR", extra=""):
    """A transform the watch animates smoothly over one second whenever its value changes."""
    return (f'<Transform target="{target}" value="{a(value)}"><Animation duration="1" interpolation="{interp}" '
            f'fps="{fps}" repeat="0"{extra}/></Transform>')


AMBIENT_OFF = '<Variant mode="AMBIENT" target="alpha" value="0"/>'


def image(name, x, y, w, h, transforms="", extra="", pivot_y=0.5):
    return (f'<PartImage x="{round(x)}" y="{round(y)}" width="{w}" height="{h}" pivotX="0.5" pivotY="{pivot_y:g}"{extra}>'
            f'{transforms}<Image resource="{res_name(name)}"/></PartImage>')


def dot(x, y, r, color, transforms=""):
    s = math.ceil(r * 2 + 2)              # parts sit on whole pixels; the ellipse inside can be fractional
    pad = (s - r * 2) / 2
    return (f'<PartDraw x="{round(x - s / 2)}" y="{round(y - s / 2)}" width="{s}" height="{s}" pivotX="0.5" pivotY="0.5">{transforms}'
            f'<Ellipse x="{pad:.2f}" y="{pad:.2f}" width="{r * 2:.2f}" height="{r * 2:.2f}"><Fill color="{color}"/></Ellipse></PartDraw>')


def font(family, size, color, template, params, slant="NORMAL", spacing=None):
    sp = f' letterSpacing="{spacing}"' if spacing is not None else ""
    ps = "".join(f'<Parameter expression="{a(p)}"/>' for p in params)
    return (f'<Font family="{family}" size="{size}" color="{color}" slant="{slant}" weight="NORMAL"{sp}>'
            f'<Template>{a(template)}{ps}</Template></Font>')


def text(box, family, size, color, template, params, slant="NORMAL", spacing=None):
    x, y, w, h = box
    return (f'<PartText x="{x}" y="{y}" width="{w}" height="{h}"><Text align="CENTER" ellipsis="TRUE">'
            f'{font(family, size, color, template, params, slant, spacing)}</Text></PartText>')


def arc_text(family, size, color, template, params, spacing):
    d = ARC_R * 2
    return (f'<PartText x="0" y="0" width="{S}" height="{S}"><TextCircular centerX="{C:g}" centerY="{C:g}" width="{d}" height="{d}" '
            f'startAngle="296" endAngle="64" direction="CLOCKWISE" align="CENTER" ellipsis="TRUE">'
            f'{font(family, size, color, template, params, spacing=spacing)}</TextCircular></PartText>')


def group(name, body, extra=""):
    return f'<Group name="{name}" x="0" y="0" width="{S}" height="{S}"{extra}>{body}</Group>'


def ring(cx, cy, d, color, width, fill=None):
    s = math.ceil(d + width + 2)
    o = (s - d) / 2
    fl = f'<Fill color="{fill}"/>' if fill else ""
    st = f'<Stroke color="{color}" thickness="{width:g}"/>' if width else ""
    return (f'<PartDraw x="{round(cx - s / 2)}" y="{round(cy - s / 2)}" width="{s}" height="{s}">'
            f'<Ellipse x="{o:.2f}" y="{o:.2f}" width="{d:.2f}" height="{d:.2f}">{fl}{st}</Ellipse></PartDraw>')


# ------------------------------------------------------------------ the four looks
def lines(st):
    """The words on the face, for one look (or the ambient style)."""
    f_arc, f_date, f_time, f_meal = st["fonts"]
    s_arc, s_date, s_time, s_meal = st["sizes"]
    c_arc, c_date, c_time, c_meal = st["colors"]
    upper = st.get("upper_arc", True)
    out = arc_text(f_arc, s_arc, c_arc, "%s · %s %s", [WD_UP if upper else WD, SHIRE_DAY, shire_name(upper)], st["spacing"][0])
    out += text(DATE_BOX, f_date, s_date, c_date, "%s %s %s", ["[DAY_OF_WEEK_S]", "[DAY]", "[MONTH_S]"], spacing=st["spacing"][1])
    out += text(TIME_BOX, f_time, s_time, c_time, "%s:%s", [HOUR, "[MINUTE_Z]"])
    if "meal" not in st.get("skip", ()):
        out += text(MEAL_BOX, f_meal, s_meal, c_meal, "%s", [MEAL], slant="ITALIC")
    return out


def plates(look):
    fill, edge, width = STYLE[look]["plate"]
    out = ""
    for _, x, y, _, _ in COMPS:
        cx, cy = x + COMP_D / 2, y + COMP_D / 2
        out += ring(cx, cy, COMP_D - width, edge, width, fill)
        if look == "shire":    # a round door: a brass knob
            out += dot(cx + 34, cy + 8, 3, "#FFE2B64A")
        if look == "redbook":  # a wax seal: an inner ring pressed into it
            out += ring(cx, cy, COMP_D - 14, "#55F3E8CD", 1)
    return out


def starlit(southern):
    rnd = random.Random(1954)
    s = image("starlit-back", 0, 0, 450, 450)
    spots = [(40, 150), (402, 170), (420, 268), (132, 46), (318, 48), (360, 130), (392, 226)]
    for x, y in spots:
        r = rnd.uniform(1.2, 2.0)
        col = rnd.choice(["#FFF4F1E8", "#FFF4F1E8", "#FFFFE2B0", "#FFBFD4FF"])
        s += dot(x, y, r, col, glide("alpha", f"50 + 205 * {wave(rnd.randint(4, 8), rnd.randint(0, 7))}", fps=10))
    # the moon, low on the left over the hills, in its real phase (0 new .. 4 full .. 7)
    mx, my = 50, 296
    s += image("moonglow", mx - 23, my - 23, 90, 90)
    idx = "(floor(([MOON_PHASE_POSITION] + 1.75) / 3.5) % 8)"
    flip = ' scaleX="-1"' if southern else ""
    cases = "".join(f'<Compare expression="m{i}">{image(f"moon{i}", mx, my, 44, 44, extra=flip)}</Compare>' for i in range(1, 8))
    exprs = "".join(f'<Expression name="m{i}"><![CDATA[{idx} == {i}]]></Expression>' for i in range(1, 8))
    s += f'<Condition><Expressions>{exprs}</Expressions>{cases}<Default>{image("moon0", mx, my, 44, 44, extra=flip)}</Default></Condition>'
    return s


def shire():
    s = image("shire-back", 0, 0, 450, 450)
    sx, sy = 352, 140
    s += image("rays", sx - 65, sy - 65, 130, 130, glide("angle", f"({T} * 2.4) % 360", fps=10, extra=' angleDirection="CLOCKWISE"'))
    s += image("sun", sx - 60, sy - 60, 120, 120)
    for name, x, y, w, h, dur in (("cloud-a", 40, 168, 100, 40, 40), ("cloud-b", 300, 226, 70, 28, 52)):   # drifting to and fro
        s += image(name, x, y, w, h, glide("x", f"{x} + 26 * sin(6.28319 * {phase(dur)})", fps=8))
    return s


def redbook():
    s = image("redbook-back", 0, 0, 450, 450)
    s += image("warmglow", 75, 84, 300, 220, glide("alpha", f"120 + 135 * {wave(9)}", fps=8))
    return s


def elven():
    rnd = random.Random(1955)
    s = image("elven-back", 0, 0, 450, 450)
    # a glint of light travels slowly round the silver rim, once a minute
    th = f"(6.28319 * {phase(60)})"
    s += image("glint", 0, 0, 24, 24, glide("x", f"{C - 12:g} + 216 * sin({th})", fps=20) + glide("y", f"{C - 12:g} - 216 * cos({th})", fps=20))
    # the star of Eärendil, low between the complications
    sx, sy = 225, 418
    s += image("halo", sx - 40, sy - 40, 80, 80, glide("alpha", f"120 + 135 * {wave(6)}", fps=10))
    s += image("glyph", sx - 16, sy - 16, 32, 32)
    for i in range(4):   # motes of light drifting up the sides
        x = rnd.choice([rnd.uniform(40, 90), rnd.uniform(360, 410)])
        y = rnd.uniform(220, 360)
        pp = phase(rnd.randint(12, 20), rnd.randint(0, 16))
        al = f"clamp({pp} / 0.2, 0, 1) * clamp((1 - {pp}) / 0.2, 0, 1)"
        s += dot(x, y, 1.4, "#FFDCEBF0", glide("y", f"{y - 2.4:.1f} - 120 * {pp}", fps=10) + glide("alpha", f"200 * {al}", fps=10))
    return s


def look_group(look):
    if look == "starlit":
        scene = (f'<BooleanConfiguration id="southern"><BooleanOption id="TRUE">{group("starlit-s", starlit(True))}</BooleanOption>'
                 f'<BooleanOption id="FALSE">{group("starlit-n", starlit(False))}</BooleanOption></BooleanConfiguration>')
    else:
        scene = {"shire": shire, "redbook": redbook, "elven": elven}[look]()
    return group(look, group(f"{look}-scene", AMBIENT_OFF + scene + plates(look)) + group(f"{look}-text", AMBIENT_OFF + lines(STYLE[look])))


def ambient_group():
    """The always-on display: thin rings for the complications, the time and the Shire date, in grey on black."""
    out = "".join(ring(x + COMP_D / 2, y + COMP_D / 2, COMP_D - 2, "#FF4A4A4A", 1.4) for _, x, y, _, _ in COMPS)
    out += lines(dict(AMBIENT, skip=("meal",)))
    return f'<Group name="ambient" x="0" y="0" width="{S}" height="{S}" alpha="0"><Variant mode="AMBIENT" target="alpha" value="255"/>{out}</Group>'


def complication(slot, x, y, provider, label):
    d = COMP_D
    icon = lambda ix, iy, s: (f'<PartImage x="{ix}" y="{iy}" width="{s}" height="{s}" tintColor="{COMP_TEXT}">'
                              f'<Image resource="[COMPLICATION.MONOCHROMATIC_IMAGE]"/></PartImage>')
    short = icon(34, 14, 32) + text((4, 48, d - 8, 38), "alegreya_sans", 31, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"])
    frac = "clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN]) / ([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN]), 0, 1)"
    arc = lambda color, extra: (f'<PartDraw x="0" y="0" width="{d}" height="{d}"><Arc centerX="{d / 2:g}" centerY="{d / 2:g}" width="{d - 12}" height="{d - 12}" startAngle="0" endAngle="360">'
                                f'{extra}<Stroke color="{color}" thickness="5" cap="ROUND"/></Arc></PartDraw>')
    ranged = (arc("#40FFFFFF", "") + arc(COMP_ACCENT, tr("endAngle", f"360 * {frac}"))
              + icon(37, 18, 26) + text((8, 44, d - 16, 36), "alegreya_sans", 28, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"]))
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
            '<BooleanConfiguration id="southern" displayName="Southern hemisphere moon" defaultValue="FALSE"/>'
            '</UserConfigurations>'
            '<Scene backgroundColor="#FF000000">'
            f'<ListConfiguration id="look">{options}</ListConfiguration>'
            + ambient_group()
            + "".join(complication(*c) for c in COMPS)
            + '</Scene></WatchFace>\n')


# ------------------------------------------------------------------ still pictures (picker preview, app backgrounds, checks)
STILLS = {
    "shire": [("shire-back", 0, 0), ("rays", 287, 75), ("sun", 292, 80), ("cloud-a", 40, 168), ("cloud-b", 300, 226)],
    "redbook": [("redbook-back", 0, 0), ("warmglow", 75, 84)],
    "starlit": [("starlit-back", 0, 0), ("moonglow", 27, 273), ("moon3", 50, 296)],
    "elven": [("elven-back", 0, 0), ("halo", 185, 378), ("glyph", 209, 402), ("glint", 360, 60)],
}
SAMPLE = {
    "shire": ("9:21", "HEVENSDAY · 30 WINTERFILTH", "Wed 21 Oct", "Second breakfast", ("80%", "4,512")),
    "redbook": ("3:30", "Hevensday · 30 Winterfilth", "Wed 21 Oct", "Afternoon tea", ("64%", "9,870")),
    "starlit": ("8:05", "HEVENSDAY · 30 WINTERFILTH", "WED 21 OCT", "Supper", ("41%", "11,204")),
    "elven": ("1:30", "HEVENSDAY · 30 WINTERFILTH", "WED 21 OCT", "The Shire sleeps", ("23%", "12,640")),
    "ambient": ("1:30", "HEVENSDAY · 30 WINTERFILTH", "WED 21 OCT", None, ("23%", "12,640")),
}


def still(look, with_words=True):
    from PIL import Image, ImageDraw, ImageFont
    src = RES / "drawable-nodpi"
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    if look in STILLS:
        for name, x, y in STILLS[look]:
            img.alpha_composite(Image.open(src / f"{res_name(name)}.png").convert("RGBA"), (x, y))
    if not with_words:
        return img
    dr = ImageDraw.Draw(img)
    fonts = RES / "font"
    hexc = lambda c: (int(c[3:5], 16), int(c[5:7], 16), int(c[7:9], 16), int(c[1:3], 16))
    st = STYLE.get(look, AMBIENT)

    def box_text(box, fam, size, col, s, spacing=0.0):
        x, y, w, h = box
        f = ImageFont.truetype(str(fonts / f"{fam}.ttf"), size)
        asc, desc = f.getmetrics()
        widths = [f.getlength(ch) for ch in s]
        total = sum(widths) + spacing * size * (len(s) - 1)
        cx = x + (w - total) / 2
        top = y + (h - (asc + desc)) / 2
        for ch, cw in zip(s, widths):
            dr.text((cx, top), ch, font=f, fill=hexc(col))
            cx += cw + spacing * size

    def curve(fam, size, col, s, spacing):
        f = ImageFont.truetype(str(fonts / f"{fam}.ttf"), size)
        asc, desc = f.getmetrics()
        widths = [f.getlength(ch) + spacing * size for ch in s]
        ang = -sum(widths) / 2 / ARC_R
        for ch, cw in zip(s, widths):
            g = Image.new("RGBA", (int(cw + 4) * 2, (asc + desc) * 2), (0, 0, 0, 0))
            ImageDraw.Draw(g).text((g.width / 2 - (cw - spacing * size) / 2, g.height / 2 - asc), ch, font=f, fill=hexc(col))
            mid = ang + cw / 2 / ARC_R
            g = g.rotate(-math.degrees(mid), resample=Image.BICUBIC)
            px, py = C + ARC_R * math.sin(mid), C - ARC_R * math.cos(mid)
            img.alpha_composite(g, (int(px - g.width / 2), int(py - g.height / 2)))
            ang += cw / ARC_R

    t, arc, date, meal, comps = SAMPLE[look]
    if look != "ambient":
        fill, edge, width = st["plate"]
        for _, x, y, _, _ in COMPS:
            dr.ellipse((x + width / 2, y + width / 2, x + COMP_D - width / 2, y + COMP_D - width / 2), fill=hexc(fill), outline=hexc(edge), width=round(width))
    else:
        for _, x, y, _, _ in COMPS:
            dr.ellipse((x, y, x + COMP_D, y + COMP_D), outline=(74, 74, 74, 255), width=1)
    curve(st["fonts"][0], st["sizes"][0], st["colors"][0], arc, st["spacing"][0])
    box_text(DATE_BOX, st["fonts"][1], st["sizes"][1], st["colors"][1], date, st["spacing"][1])
    box_text(TIME_BOX, st["fonts"][2], st["sizes"][2], st["colors"][2], t)
    if meal:
        box_text(MEAL_BOX, st["fonts"][3], st["sizes"][3], st["colors"][3], meal)
    for (_, x, y, _, _), v in zip(COMPS, comps):
        dr.ellipse((x + 42, y + 18, x + 58, y + 34), outline=hexc(COMP_TEXT), width=2)
        box_text((x + 4, y + 48, COMP_D - 8, 38), "alegreya_sans", 31, COMP_TEXT, v)
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
        for look in STILLS:
            still(look, with_words=False).convert("RGB").save(out / f"wl_{look}.png", optimize=True)
        Image.open(nodpi / "wf_preview.png").save(out / "tile_preview.png")
    if PREVIEW:
        p = Path(PREVIEW)
        p.mkdir(parents=True, exist_ok=True)
        sheet = Image.new("RGB", (S * 5 + 40, S + 20), (40, 40, 40))
        for i, look in enumerate(["shire", "redbook", "starlit", "elven", "ambient"]):
            sheet.paste(still(look).convert("RGB"), (10 + i * (S + 5), 10))
        sheet.save(p / "faces.png")


async def main():
    await render()
    make_static_fonts()
    write_stills(ARGS[1] if len(ARGS) > 1 else None)
    raw = RES / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    xml = watchface_xml()
    (raw / "watchface.xml").write_text(xml, encoding="utf-8")
    print(f"watchface.xml: {len(xml) // 1024} KB, {len(PARTS)} images")


if __name__ == "__main__":
    asyncio.run(main())
