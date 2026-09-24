"""Color parsing, formatting, and HLS-space math.

Ported from the original one-off scripts this project replaced. colorsys (stdlib) is used so the
math matches what those scripts did (the R version reimplemented the same colorsys algorithm by
hand to match this exactly).
"""
from __future__ import annotations

import colorsys
import math
import re

NAMED = {"transparent": (0, 0, 0, 0.0), "black": (0, 0, 0, 1.0), "white": (255, 255, 255, 1.0)}
_NUM = r"\s*([-+]?[\d.]+%?)\s*"

RGBA = tuple[float, float, float, float]


def _rnd(x: float) -> int:
    """Round half up."""
    return math.floor(x + 0.5)


def parse_color(s: object) -> RGBA | None:
    """Return (r, g, b, a) with r,g,b in 0-255 and a in 0-1, or None if not a color."""
    if not isinstance(s, str):
        return None
    t = s.strip().lower()
    if t in NAMED:
        return NAMED[t]
    m = re.fullmatch(r"#([0-9a-f]{3,8})", t)
    if m:
        h = m.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = re.fullmatch(r"rgba?\(" + _NUM + "," + _NUM + "," + _NUM + r"(?:," + _NUM + r")?\)", t)
    if m:

        def ch(v: str) -> float:
            return float(v[:-1]) * 2.55 if v.endswith("%") else float(v)

        r, g, b = (ch(m.group(i)) for i in (1, 2, 3))
        a_s = m.group(4)
        a = 1.0 if a_s is None else (float(a_s[:-1]) / 100 if a_s.endswith("%") else float(a_s))
        return (r, g, b, a)
    m = re.fullmatch(r"hsla?\(" + _NUM + "," + _NUM + "," + _NUM + r"(?:," + _NUM + r")?\)", t)
    if m:
        hh = float(m.group(1).rstrip("%")) / 360
        ss = float(m.group(2).rstrip("%")) / 100
        ll = float(m.group(3).rstrip("%")) / 100
        r, g, b = colorsys.hls_to_rgb(hh % 1, ll, ss)
        a_s = m.group(4)
        a = 1.0 if a_s is None else (float(a_s[:-1]) / 100 if a_s.endswith("%") else float(a_s))
        return (r * 255, g * 255, b * 255, a)
    return None


def fmt_color(r: float, g: float, b: float, a: float = 1.0) -> str:
    r, g, b = (max(0, min(255, _rnd(v))) for v in (r, g, b))
    a = max(0.0, min(1.0, a))
    if a >= 0.9995:
        return f"#{r:02x}{g:02x}{b:02x}"
    a = math.floor(a * 1000 + 0.5) / 1000
    return f"rgba({r},{g},{b},{a:g})"


def hex_key(c: RGBA) -> str:
    """#RRGGBB uppercase, alpha ignored - used for match.paint regexes."""
    r, g, b, _ = c
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, _rnd(v))) for v in (r, g, b)))


def to_hls(c: RGBA) -> tuple[float, float, float]:
    r, g, b, _ = c
    return colorsys.rgb_to_hls(r / 255, g / 255, b / 255)


def from_hls(h: float, l: float, s: float, a: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return fmt_color(r * 255, g * 255, b * 255, a)


def invert_lightness(c: RGBA) -> RGBA:
    """Flip lightness (l' = 1 - l) keeping hue and saturation. Used for sprite pixels."""
    a = c[3]
    h, l, s = to_hls(c)
    nr, ng, nb = colorsys.hls_to_rgb(h, 1 - l, s)
    return (nr * 255, ng * 255, nb * 255, a)
