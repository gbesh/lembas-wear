"""English in Tengwar (a simple general-use tehtar mode), for Lembas's optional Elvish script.

Letters map to tengwar by sound-ish spelling (th, sh, ch, ng, wh, ph as single letters); each vowel
rides as a tehta on the consonant after it (on a short carrier when no consonant follows), a final
silent e is a dot under the last letter, doubled letters get a bar beneath, and n or m before a stop
is a bar over it. Digits are Tengwar numerals. Codepoints are the Free Tengwar / CSUR layout that
Alcarin Tengwar uses. The same rules are in the phone app (Tengwar.kt) and Lembas for Windows; here they write the watch
face's Tengwar weekdays.
"""

C = {  # consonants
    "th": 0xE008, "sh": 0xE00A, "ch": 0xE002, "ng": 0xE012, "wh": 0xE029, "ph": 0xE009, "ck": 0xE003, "qu": 0xE003,
    "t": 0xE000, "p": 0xE001, "k": 0xE003, "c": 0xE003, "d": 0xE004, "b": 0xE005, "j": 0xE006, "g": 0xE007,
    "f": 0xE009, "v": 0xE00D, "n": 0xE010, "m": 0xE011, "w": 0xE015, "l": 0xE022, "s": 0xE024, "z": 0xE026,
    "h": 0xE028, "r": 0xE014, "x": 0xE003, "y": 0xE016,
}
V = {"a": 0xE040, "e": 0xE046, "i": 0xE044, "o": 0xE04A, "u": 0xE04C, "y": 0xE044}
ROMEN, ORE, SILME, SILME_N, ESSE, ESSE_N = 0xE020, 0xE014, 0xE024, 0xE025, 0xE026, 0xE027
SHORT, LONG = 0xE02E, 0xE02C
DOT_BELOW, DOUBLER, NASAL, DOUBLE_ACUTE = 0xE045, 0xE051, 0xE050, 0xE048
STOPS = {0xE000, 0xE001, 0xE002, 0xE003, 0xE004, 0xE005, 0xE006, 0xE007}
DIGIT0 = 0xE070


def _units(w):
    """A word as a list of ['C', code, marks] / ['V', tehta, long]."""
    out, i = [], 0
    vowels = "aeiou"
    while i < len(w):
        ch = w[i]
        nxt = w[i + 1] if i + 1 < len(w) else ""
        if ch == "y":   # a consonant before a vowel, otherwise a vowel
            if nxt and nxt in vowels:
                out.append(["C", C["y"], []]); i += 1; continue
            out.append(["V", V["y"], False]); i += 1; continue
        if ch in vowels:
            if nxt == ch and ch in "eo":   # ee, oo: long
                out.append(["V", V[ch], True]); i += 2; continue
            out.append(["V", V[ch], False]); i += 1; continue
        if w[i:i + 2] == "gh":
            i += 2; continue
        two = w[i:i + 2]
        if two in C and two != ch * 2:
            out.append(["C", C[two], []]); i += 2; continue
        if ch == "c" and nxt in ("e", "i", "y"):
            out.append(["C", SILME, []]); i += 1; continue
        if ch == "x":
            out.append(["C", C["k"], []]); out.append(["C", SILME, []]); i += 1; continue
        if ch in C:
            if nxt == ch:   # a doubled letter: once, with a bar beneath
                out.append(["C", C[ch], [DOUBLER]]); i += 2; continue
            out.append(["C", C[ch], []]); i += 1; continue
        i += 1   # anything else is dropped
    return out


def word(w):
    w = w.lower()
    if w.isdigit():
        return "".join(chr(DIGIT0 + int(d)) for d in w)
    u = _units(w)
    # a silent e at the end of a word, after a consonant: a dot under that consonant
    silent = len(u) >= 3 and u[-1][0] == "V" and u[-1][1] == V["e"] and not u[-1][2] and u[-2][0] == "C" and w.endswith("e")
    if silent:
        u.pop(); u[-1][2].append(DOT_BELOW)
    # n or m before a stop: a bar over the stop
    k = 0
    while k < len(u) - 1:
        if u[k][0] == "C" and u[k][1] in (C["n"], C["m"]) and not u[k][2] and u[k + 1][0] == "C" and u[k + 1][1] in STOPS:
            u[k + 1][2].append(NASAL); u.pop(k); continue
        k += 1
    # r: rómen before a vowel, órë otherwise
    for k, x in enumerate(u):
        if x[0] == "C" and x[1] == ORE and k + 1 < len(u) and u[k + 1][0] == "V":
            x[1] = ROMEN
    out = []
    k = 0
    while k < len(u):
        x = u[k]
        if x[0] == "V":
            tehta = DOUBLE_ACUTE if (x[2] and x[1] == V["e"]) else x[1]
            nxt = u[k + 1] if k + 1 < len(u) else None
            if nxt is not None and nxt[0] == "C" and not x[2]:
                code = nxt[1]
                if code == SILME: code = SILME_N
                if code == ESSE: code = ESSE_N
                out.append(chr(code) + chr(tehta) + "".join(chr(m) for m in nxt[2]))
                k += 2; continue
            out.append(chr(LONG if x[2] else SHORT) + chr(tehta))
            k += 1; continue
        out.append(chr(x[1]) + "".join(chr(m) for m in x[2]))
        k += 1
    return "".join(out)


def text(s):
    """A phrase in Tengwar: words and numbers; spaces as they are, ':' as a double stop, ',' as a stop."""
    import re
    return "".join(word(t) if re.fullmatch(r"[A-Za-z]+|\d+", t) else t.replace(":", "\uE061").replace(",", "\uE060")
                   for t in re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", s))


if __name__ == "__main__":
    import sys
    for s in sys.argv[1:] or ["Saturday 7 November", "Monday", "Wednesday", "Thursday", "the Shire", "Hobbit Day", "Rivendell"]:
        print(s, " ".join("%04X" % ord(c) for c in text(s)))
