#!/usr/bin/env python3
"""Generate dark.css for the ISPConfig dark theme.

Walks every stylesheet the panel loads, in the same order main.tpl.htm loads
them, and mirrors every color-bearing declaration with its color remapped to a
dark palette. Loaded after the originals with identical selectors, so the
cascade (order, specificity, !important) is preserved exactly — only colors
change. Nothing color-related in the original CSS can be missed this way.

Hand-written fixes (inline template styles, logo, catch-all) live in
dark-extra.css, not here.

Usage: tools/build-dark.py            (writes dark/assets/stylesheets/dark.css)
       tools/build-dark.py --report   (also prints per-file counts)
"""
import colorsys
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "dark" / "assets" / "stylesheets"
OUT = CSS / "dark.css"

# Same order as the <link> tags in main.tpl.htm (login.css is layout-only).
SOURCES = [
    "bootstrap.min.css",
    "ispconfig.css",
    "pushy.css",
    "bootstrap-datetimepicker.min.css",
    "responsive.css",
    "themes/default/theme.css",
    "select2.css",
    "select2-bootstrap.css",
]

COLOR_PROPS = re.compile(
    r"^(color|background(-color|-image)?|border(-(top|right|bottom|left))?(-color)?"
    r"|outline(-color)?|fill|stroke|caret-color|column-rule(-color)?)$"
)
# Dark shadows are kept; only light ones (white emboss effects) are remapped,
# since inverting a dark shadow turns it into a glow.
SHADOW_PROPS = re.compile(r"^(-webkit-)?(box|text)-shadow$")

NAMED = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (255, 0, 0),
    "gray": (128, 128, 128), "grey": (128, 128, 128), "silver": (192, 192, 192),
    "whitesmoke": (245, 245, 245), "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211), "darkgray": (169, 169, 169),
    "green": (0, 128, 0), "blue": (0, 0, 255), "yellow": (255, 255, 0),
    "orange": (255, 165, 0), "navy": (0, 0, 128),
}
COLOR_TOKEN = re.compile(
    r"#[0-9a-fA-F]{8}\b|#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3,4}\b"
    r"|rgba?\([^)]*\)|hsla?\([^)]*\)"
    r"|\b(" + "|".join(NAMED) + r")\b",
    re.I,
)

# Palette, modeled on rjc3rd's original dark theme: neutral greys, flat
# two-tone surfaces, medium-grey borders.
PAGE_L = 0.125      # white page/panel fills -> #202020
SURFACE_L = 0.25    # white fills on controls/tabs/sidebar -> #404040
BORDER_L = 0.40     # light grey borders -> #666666

# Rules whose light fills are "raised" controls rather than page/panel area.
SURFACE_SEL = re.compile(
    r"\.form-control|\.btn-default|\.formbutton-default|#searchform button"
    r"|#main-navigation a|#sidebar(?!\s*header)|\.modules \.button"
    r"|\.content-tab-wrapper \.nav-tabs(?!\s*\.active)(?!\s*>)"
    r"|\.select2-choice|\.select2-choices|\.input-group-addon"
    r"|\.dropdown-menu|\.pagination"
)


def parse(tok):
    t = tok.lower()
    if t in NAMED:
        return NAMED[t] + (None,)
    if t.startswith("#"):
        h = t[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else None
        return r, g, b, a
    if t.startswith("rgb"):
        parts = [p.strip() for p in t[t.index("(") + 1:-1].split(",")]
        if len(parts) < 3 or any("%" in p or "var" in p for p in parts):
            return None
        r, g, b = (int(float(p)) for p in parts[:3])
        a = float(parts[3]) if len(parts) > 3 else None
        return r, g, b, a
    return None  # hsl() etc: left untouched


def hls(rgb):
    return colorsys.rgb_to_hls(*(c / 255 for c in rgb))


def fmt(r, g, b, a):
    if a is None or a >= 1:
        return "#%02x%02x%02x" % (r, g, b)
    return "rgba(%d, %d, %d, %s)" % (r, g, b, ("%.3f" % a).rstrip("0").rstrip("."))


def remap(tok, prop, surface=False):
    p = parse(tok)
    if p is None:
        return tok
    r, g, b, a = p
    h, l, s = hls((r, g, b))
    if a is not None and a == 0:
        return tok  # transparent stays transparent
    if prop == "color" and l > 0.85:
        return tok  # white text only ever sat on a dark/colored fill
    if prop.startswith("background") and 0.3 < l < 0.6 and s < 0.12:
        return tok  # mid-grey fills (badges, labels) already work on dark
    neutral = (max(r, g, b) - min(r, g, b)) / 255 < 0.06  # near-grey
    if neutral and prop.startswith("border") and l > 0.5:
        nl = BORDER_L
    elif neutral and surface and prop.startswith("background") and l > 0.6:
        # Raised control: near-white -> flat #404040; darker original states
        # (hover, active) come out lighter, as raised surfaces do on dark.
        nl = SURFACE_L + max(0, 0.93 - l) * 1.5
    else:
        # Lightness inversion: white -> #202020 page, black -> #ececec text.
        nl = (0.925 + PAGE_L - 0.125) - 0.8 * l
    if neutral:
        s = 0
    elif l > 0.8:
        s *= 0.55  # pastel backgrounds -> muted dark tints, not neon mud
    if prop == "color" and s > 0.25 and nl < 0.62:
        nl = 0.62  # keep saturated text readable on the dark page
    nr, ng, nb = (round(c * 255) for c in colorsys.hls_to_rgb(h, max(0, min(1, nl)), s))
    return fmt(nr, ng, nb, a)


def is_accent(tok):
    """A saturated mid-tone fill (btn-primary, label-danger, ...)."""
    p = parse(tok)
    if p is None or p[3] == 0:
        return False
    h, l, s = hls(p[:3])
    return s > 0.35 and 0.25 < l < 0.72


def lightness(tok):
    p = parse(tok)
    if p is None or p[3] == 0:
        return None
    return hls(p[:3])[1]


def luminance(rgb):
    def ch(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def darken_for_white(tok, target=4.5):
    """Darken a fill until white text on it meets `target` contrast.

    Fills that already pass are unchanged. Ones that don't are pulled below
    the threshold in proportion to how light they were, so a hover state
    that was darker than its base stays darker.
    """
    p = parse(tok)
    if p is None or p[3] == 0:
        return tok
    r, g, b, a = p
    h, l, s = hls((r, g, b))
    if 1.05 / (luminance((r, g, b)) + 0.05) >= target:
        return tok
    lo, hi = 0.0, l  # largest lightness that passes
    for _ in range(20):
        mid = (lo + hi) / 2
        rgb = [c * 255 for c in colorsys.hls_to_rgb(h, mid, s)]
        if 1.05 / (luminance(rgb) + 0.05) >= target:
            lo = mid
        else:
            hi = mid
    nl = max(0.12, lo * (1 - 0.6 * max(0, 0.72 - l)))
    nr, ng, nb = (round(c * 255) for c in colorsys.hls_to_rgb(h, nl, s))
    return fmt(nr, ng, nb, a)


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def blocks(css):
    """Yield (prelude, body) for each top-level {} block; nested bodies raw."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        prelude = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        yield prelude, css[j + 1:k - 1]
        i = k


def decls(body):
    for d in body.split(";"):
        if ":" not in d:
            continue
        prop, val = d.split(":", 1)
        prop = prop.strip().lower()
        val = val.strip()
        if prop and val:
            yield prop, val


def convert_rule(sel, body, stats):
    ds = list(decls(body))
    color_ds = [(p, v) for p, v in ds
                if (COLOR_PROPS.match(p) or SHADOW_PROPS.match(p))
                and COLOR_TOKEN.search(v) and "progid" not in v]
    if not color_ds:
        return None

    def toks(pred):
        return [m.group(0) for p, v in color_ds if pred(p)
                for m in COLOR_TOKEN.finditer(v)]
    bg = [t for t in toks(lambda p: p.startswith("background"))
          if lightness(t) is not None]
    text_l = [lightness(t) for t in toks(lambda p: p == "color")]
    light_text = any(l is not None and l > 0.85 for l in text_l)

    # Rules are never dropped, only passed through unchanged, so a kept rule
    # still beats earlier same-specificity rules exactly as it did before.
    if bg and light_text and all(lightness(t) < 0.5 for t in bg):
        # Already light-on-dark (dark table headers, tooltips, badges).
        mode = "keep"
        stats["dark_kept"] += 1
    elif any(is_accent(t) for t in bg):
        # Saturated fill (buttons, labels, progress bars): keep the hue,
        # darken just enough for white text to stay readable.
        mode = "accent"
        stats["accent"] += 1
    else:
        mode = "remap"

    out = []
    for p, v in color_ds:
        if mode == "keep" or (SHADOW_PROPS.match(p) and mode == "accent"):
            nv = v
        elif mode == "accent":
            nv = v if p == "color" else COLOR_TOKEN.sub(
                lambda m: darken_for_white(m.group(0)), v)
        elif SHADOW_PROPS.match(p):
            nv = COLOR_TOKEN.sub(
                lambda m: remap(m.group(0), p)
                if (lightness(m.group(0)) or 0) > 0.7 else m.group(0), v)
        else:
            surf = bool(SURFACE_SEL.search(sel))
            nv = COLOR_TOKEN.sub(lambda m: remap(m.group(0), p, surf), v)
        out.append("  %s: %s;" % (p, nv))
        stats["decls"] += 1
    stats["rules"] += 1
    return "%s {\n%s\n}" % (re.sub(r"\s+", " ", sel), "\n".join(out))


def convert(css, stats):
    out = []
    for prelude, body in blocks(strip_comments(css)):
        low = prelude.lower()
        if low.startswith("@media"):
            if "print" in low and "screen" not in low:
                continue
            inner = convert(body, stats)
            if inner:
                out.append("%s {\n%s\n}" % (re.sub(r"\s+", " ", prelude),
                                             inner))
        elif low.startswith("@"):
            continue  # @font-face, @keyframes, @-ms-viewport, ...
        else:
            r = convert_rule(prelude, body, stats)
            if r:
                out.append(r)
    return "\n".join(out)


def main():
    report = "--report" in sys.argv
    parts = [
        "/* GENERATED by tools/build-dark.py — do not edit by hand.",
        " * Color-only mirror of the panel's stylesheets, remapped to dark.",
        " * Hand-written fixes go in dark-extra.css. */",
        ":root { color-scheme: dark; }",
    ]
    for name in SOURCES:
        stats = {"rules": 0, "decls": 0, "accent": 0, "dark_kept": 0}
        body = convert((CSS / name).read_text(encoding="utf-8"), stats)
        parts.append("\n/* ---- %s ---- */\n%s" % (name, body))
        if report:
            print("%-36s %4d rules  %4d decls  %3d accent  %3d already-dark"
                  % (name, stats["rules"], stats["decls"], stats["accent"],
                     stats["dark_kept"]))
    OUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
