"""Build the Lembas watch face (Watch Face Format) for round Wear OS watches.

Renders the backgrounds and sprites from wear/art/watch.html, makes fixed-weight copies of the
fonts, then writes watchface/src/main/res/raw/watchface.xml. Everything that moves is described
declaratively, so the watch's own renderer animates it (and stops in ambient mode); there is no
code on the watch.

The design: deep tonal (or black) backgrounds in the four Lembas palettes; large stacked numerals,
the hours heavy in the look's colour and the minutes light; a complication either side; and a
24-hour sun ring around the rim, where the sun (or tonight's moon) travels from sunrise on the
left, over noon at the top, to sunset on the right. The Shire date and the hobbit mealtime sit
above and below the time as quiet lines of type.

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
    "shire-back": (450, 450), "redbook-back": (450, 450), "starlit-back": (450, 450), "elven-back": (450, 450),
    "ticks": (450, 450), "ticks-major": (450, 450), "arc-day": (450, 450), "arc-night": (450, 450),
    "sun": (40, 40), "moonhalo": (40, 40), **{f"moon{i}": (18, 18) for i in range(8)},
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


HOUR_Z = "([IS_24_HOUR_MODE] ? [HOUR_0_23_Z] : [HOUR_1_12_Z])"

# ------------------------------------------------------------------ layout
DATE_BOX = (100, 58, 250, 32)      # Wed 21
LORE_BOX = (60, 88, 330, 30)       # Hevensday · 30 Winterfilth
HOURS_BOX = (90, 112, 270, 124)
MINS_BOX = (90, 224, 270, 124)
MEAL_BOX = (80, 348, 290, 30)
RING_R = 209                       # where the sun and moon travel
COMP_D = 80
COMPS = [(0, 38, 185, "WATCH_BATTERY", "Left"), (1, 332, 185, "STEP_COUNT", "Right")]
NUM_SIZE = 150

# Each look: hours (accent), minutes and date (text), Shire date, mealtime, the daylight half of
# the ring, the night half, the ticks, and the complication background.
STYLE = {
    "shire": dict(back="shire-back", hours="#FFF2D06B", text="#FFF1F4E6", lore="#FFB9D79A", meal="#FFA3B59B",
                  day="#CCF2D06B", night="#4DB9D79A", ticks="#99F1F4E6", plate="#2EB9D79A"),
    "redbook": dict(back="redbook-back", hours="#FFF07A62", text="#FFF6ECD6", lore="#FFE6C79A", meal="#FFC2A08A",
                    day="#CCF07A62", night="#4DF6ECD6", ticks="#99F6ECD6", plate="#2EF07A62"),
    "starlit": dict(back="starlit-back", hours="#FFE9CC88", text="#FFF6F0E2", lore="#FFA9BCE6", meal="#FF8E97B0",
                    day="#99E9CC88", night="#66A9BCE6", ticks="#80F6F0E2", plate="#24FFFFFF"),
    "elven": dict(back="elven-back", hours="#FFC6DDE8", text="#FFF4F7F8", lore="#FFA2B3BB", meal="#FF7F8C93",
                  day="#80C6DDE8", night="#59C6DDE8", ticks="#73F4F7F8", plate="#1FFFFFFF"),
}
AMBIENT = dict(hours="#FFB4B4B4", text="#FFD2D2D2", lore="#FF8A8A8A", ticks="#FF6A6A6A")
COMP_TEXT = "#FFF4F4F4"


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


def image(name, x, y, w, h, transforms="", extra=""):
    return (f'<PartImage x="{round(x)}" y="{round(y)}" width="{w}" height="{h}" pivotX="0.5" pivotY="0.5"{extra}>'
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


def text(box, family, size, color, template, params, slant="NORMAL", spacing=None):
    x, y, w, h = box
    return (f'<PartText x="{x}" y="{y}" width="{w}" height="{h}"><Text align="CENTER" ellipsis="TRUE">'
            f'{font(family, size, color, template, params, slant, spacing)}</Text></PartText>')


def group(name, body, extra=""):
    return f'<Group name="{name}" x="0" y="0" width="{S}" height="{S}"{extra}>{body}</Group>'


def disc(cx, cy, d, fill):
    s = math.ceil(d + 2)
    o = (s - d) / 2
    return (f'<PartDraw x="{round(cx - s / 2)}" y="{round(cy - s / 2)}" width="{s}" height="{s}">'
            f'<Ellipse x="{o:.2f}" y="{o:.2f}" width="{d:.2f}" height="{d:.2f}"><Fill color="{fill}"/></Ellipse></PartDraw>')


def tinted(name, color):
    return image(name, 0, 0, S, S, extra=f' tintColor="{color}"')


# ------------------------------------------------------------------ the face
def ring_xy(w):
    """x and y (for a sprite w wide) on the sun ring for the time of day: midnight at the bottom, noon at the top."""
    ang = f"rad({MINS} * 0.25 + 180)"
    return f"{C - w / 2:g} + {RING_R} * sin({ang})", f"{C - w / 2:g} - {RING_R} * cos({ang})"


def moon(southern):
    mx, my = ring_xy(18)
    idx = "(floor(([MOON_PHASE_POSITION] + 1.75) / 3.5) % 8)"
    flip = ' scaleX="-1"' if southern else ""
    moon_img = lambda i: image(f"moon{i}", 0, 0, 18, 18, glide("x", mx) + glide("y", my), extra=flip)
    cases = "".join(f'<Compare expression="m{i}">{moon_img(i)}</Compare>' for i in range(1, 8))
    exprs = "".join(f'<Expression name="m{i}"><![CDATA[{idx} == {i}]]></Expression>' for i in range(1, 8))
    return f'<Condition><Expressions>{exprs}</Expressions>{cases}<Default>{moon_img(0)}</Default></Condition>'


def sky_marker():
    """The sun on the ring by day; by night, the moon in tonight's phase (mirrored in the south)."""
    sx, sy = ring_xy(40)
    sun = image("sun", 0, 0, 40, 40, glide("x", sx) + glide("y", sy) + glide("alpha", f"200 + 55 * {wave(6)}", fps=8))
    hx, hy = ring_xy(40)
    night = (image("moonhalo", 0, 0, 40, 40, glide("x", hx) + glide("y", hy))
             + group("moon", f'<BooleanConfiguration id="southern"><BooleanOption id="TRUE">{group("moon-s", moon(True))}</BooleanOption>'
                             f'<BooleanOption id="FALSE">{group("moon-n", moon(False))}</BooleanOption></BooleanConfiguration>'))
    return (f'<Condition><Expressions><Expression name="day"><![CDATA[{IS_DAY} == 1]]></Expression></Expressions>'
            f'<Compare expression="day">{sun}</Compare><Default>{group("night", night)}</Default></Condition>')


def twinkles(look):
    if look not in ("starlit", "elven"):
        return ""
    rnd = random.Random(7 if look == "starlit" else 8)
    spots = [(118, 64), (334, 70), (64, 132), (390, 140), (70, 318), (384, 312)]
    return "".join(dot(x, y, rnd.uniform(1.1, 1.7), "#FFF4F1E8", glide("alpha", f"40 + 215 * {wave(rnd.randint(4, 8), rnd.randint(0, 7))}", fps=8))
                   for x, y in spots)


def words(st, ambient=False):
    out = text(DATE_BOX, "alegreya_sans", 24, st["text"], "%s %s", ["[DAY_OF_WEEK_S]", "[DAY]"], spacing=0.02)
    out += text(LORE_BOX, "lore_italic", 21, st["lore"], "%s · %s %s", [WD, SHIRE_DAY, shire_name()], slant="ITALIC")
    out += text(HOURS_BOX, "numerals_light" if ambient else "numerals_heavy", NUM_SIZE, st["hours"], "%s", [HOUR_Z])
    out += text(MINS_BOX, "numerals_light", NUM_SIZE, st["text"], "%s", ["[MINUTE_Z]"])
    if not ambient:
        out += text(MEAL_BOX, "lore_italic", 20, st["meal"], "%s", [MEAL], slant="ITALIC")
    return out


def look_group(look):
    st = STYLE[look]
    scene = image(st["back"], 0, 0, S, S) + twinkles(look)
    scene += tinted("arc-night", st["night"]) + tinted("arc-day", st["day"]) + tinted("ticks", st["ticks"])
    scene += "".join(disc(x + COMP_D / 2, y + COMP_D / 2, COMP_D, st["plate"]) for _, x, y, _, _ in COMPS)
    scene += sky_marker()
    return group(look, group(f"{look}-scene", AMBIENT_OFF + scene) + group(f"{look}-text", AMBIENT_OFF + words(st)))


def ambient_group():
    """The always-on display: the hours and minutes in light grey numerals, the four main ticks and the date."""
    out = tinted("ticks-major", AMBIENT["ticks"]) + words(AMBIENT, ambient=True)
    return f'<Group name="ambient" x="0" y="0" width="{S}" height="{S}" alpha="0"><Variant mode="AMBIENT" target="alpha" value="255"/>{out}</Group>'


def complication(slot, x, y, provider, label):
    d = COMP_D
    icon = lambda ix, iy, s: (f'<PartImage x="{ix}" y="{iy}" width="{s}" height="{s}" tintColor="{COMP_TEXT}">'
                              f'<Image resource="[COMPLICATION.MONOCHROMATIC_IMAGE]"/></PartImage>')
    short = icon(28, 12, 24) + text((4, 38, d - 8, 30), "alegreya_sans", 25, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"])
    frac = "clamp(([COMPLICATION.RANGED_VALUE_VALUE] - [COMPLICATION.RANGED_VALUE_MIN]) / ([COMPLICATION.RANGED_VALUE_MAX] - [COMPLICATION.RANGED_VALUE_MIN]), 0, 1)"
    arc = lambda color, extra: (f'<PartDraw x="0" y="0" width="{d}" height="{d}"><Arc centerX="{d / 2:g}" centerY="{d / 2:g}" width="{d - 6}" height="{d - 6}" startAngle="0" endAngle="360">'
                                f'{extra}<Stroke color="{color}" thickness="4" cap="ROUND"/></Arc></PartDraw>')
    ranged = (arc("#33FFFFFF", "") + arc(COMP_TEXT, tr("endAngle", f"360 * {frac}"))
              + icon(29, 13, 22) + text((8, 36, d - 16, 28), "alegreya_sans", 23, COMP_TEXT, "%s", ["[COMPLICATION.TEXT]"]))
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
SAMPLE = {   # look: (time minutes past midnight, hours, minutes, date, Shire date, meal, complications)
    "shire": (561, "09", "21", "Wed 21", "Hevensday · 30 Winterfilth", "Second breakfast", ("80%", "4,512")),
    "redbook": (930, "03", "30", "Wed 21", "Hevensday · 30 Winterfilth", "Afternoon tea", ("64%", "9,870")),
    "starlit": (1205, "08", "05", "Wed 21", "Hevensday · 30 Winterfilth", "Supper", ("41%", "11,204")),
    "elven": (90, "01", "30", "Wed 21", "Hevensday · 30 Winterfilth", "The Shire sleeps", ("23%", "12,640")),
    "ambient": (90, "01", "30", "Wed 21", "Hevensday · 30 Winterfilth", None, ("23%", "12,640")),
}


def still(look, with_words=True):
    from PIL import Image, ImageDraw, ImageFont
    src = RES / "drawable-nodpi"
    fonts = RES / "font"
    hexc = lambda c: (int(c[3:5], 16), int(c[5:7], 16), int(c[7:9], 16), int(c[1:3], 16))
    img = Image.new("RGBA", (S, S), (0, 0, 0, 255))
    load = lambda n: Image.open(src / f"{res_name(n)}.png").convert("RGBA")

    def tint(n, col):
        im = load(n)
        r, g, b, al = hexc(col)
        solid = Image.new("RGBA", im.size, (r, g, b, 255))
        solid.putalpha(Image.eval(im.getchannel("A"), lambda v: v * al // 255))
        img.alpha_composite(solid)

    mins, hh, mm, date, lore, meal, comps = SAMPLE[look]
    st = STYLE.get(look)
    if st:
        img.alpha_composite(load(st["back"]))
        tint("arc-night", st["night"]); tint("arc-day", st["day"]); tint("ticks", st["ticks"])
    else:
        st = AMBIENT
        tint("ticks-major", AMBIENT["ticks"])
    if not with_words:
        return img
    dr = ImageDraw.Draw(img)
    if look != "ambient":
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        for _, x, y, _, _ in COMPS:
            ImageDraw.Draw(layer).ellipse((x, y, x + COMP_D, y + COMP_D), fill=hexc(st["plate"]))
        img.alpha_composite(layer)
        ang = math.radians(mins * 0.25 + 180)
        day = 360 <= mins < 1080
        n = "sun" if day else "moon3"
        w = 40 if day else 18
        if not day:
            img.alpha_composite(load("moonhalo"), (int(C - 20 + RING_R * math.sin(ang)), int(C - 20 - RING_R * math.cos(ang))))
        img.alpha_composite(load(n), (int(C - w / 2 + RING_R * math.sin(ang)), int(C - w / 2 - RING_R * math.cos(ang))))

    def box_text(box, fam, size, col, s):
        x, y, w, h = box
        f = ImageFont.truetype(str(fonts / f"{fam}.ttf"), size)
        asc, desc = f.getmetrics()
        tw = f.getlength(s)
        dr.text((x + (w - tw) / 2, y + (h - (asc + desc)) / 2), s, font=f, fill=hexc(col))

    amb = look == "ambient"
    box_text(DATE_BOX, "alegreya_sans", 24, st["text"], date)
    box_text(LORE_BOX, "lore_italic", 21, st["lore"], lore)
    box_text(HOURS_BOX, "numerals_light" if amb else "numerals_heavy", NUM_SIZE, st["hours"], hh)
    box_text(MINS_BOX, "numerals_light", NUM_SIZE, st["text"], mm)
    if meal:
        box_text(MEAL_BOX, "lore_italic", 20, st["meal"], meal)
    if not amb:
        for (_, x, y, _, _), v in zip(COMPS, comps):
            dr.ellipse((x + 33, y + 15, x + 47, y + 31), outline=hexc(COMP_TEXT), width=2)
            box_text((x + 4, y + 38, COMP_D - 8, 30), "alegreya_sans", 25, COMP_TEXT, v)
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
        for look in STYLE:   # the watch app's backgrounds: the look's light, without the words
            Image.open(nodpi / f"{res_name(STYLE[look]['back'])}.png").convert("RGB").save(out / f"wl_{look}.png", optimize=True)
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
