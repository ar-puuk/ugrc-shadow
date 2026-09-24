"""The restyling engine: applies a service's regex rules to a MapLibre style's layers.

Ported 1:1 (behavior-for-behavior) from the original one-off script this project replaced.
"""
from __future__ import annotations

import copy
import re

from ugrc_shadow.colors import fmt_color, from_hls, hex_key, parse_color, to_hls

TYPE_PREFIX = {
    "fill": ("fill-",),
    "line": ("line-",),
    "symbol": ("text-", "icon-"),
    "circle": ("circle-",),
    "background": ("background-",),
    "fill-extrusion": ("fill-extrusion-",),
    "heatmap": ("heatmap-",),
    "raster": ("raster-",),
    "hillshade": ("hillshade-",),
}


def prop_ok(layer_type: str, prop: str) -> bool:
    pre = TYPE_PREFIX.get(layer_type, ())
    if layer_type == "fill" and prop.startswith("fill-extrusion-"):
        return False
    return prop.startswith(pre)


def is_color_prop(prop: str) -> bool:
    return prop.endswith("-color")


class Shadower:
    """Rewrites a style's layers according to a service's rules + a resolved palette dict."""

    def __init__(self, palette: dict, fallback: dict):
        self.palette = palette
        self.fb = fallback

    # -- value resolution ----------------------------------------------------
    def ref(self, v):
        """Resolve '@name' palette references, recursively inside arrays."""
        if isinstance(v, str) and v.startswith("@"):
            name = v[1:]
            if name not in self.palette:
                raise KeyError("palette entry not found: " + v)
            return self.ref(self.palette[name])
        if isinstance(v, list):
            return [self.ref(x) for x in v]
        return v

    def color_value(self, spec, original, keep_alpha):
        orig = parse_color(original)
        if isinstance(spec, dict) and "tint" in spec:
            if orig is None:
                return self.walk_colors(original, lambda c: self.tint(c, spec["tint"]))
            return self.tint(orig, spec["tint"])
        if isinstance(spec, dict) and "color" in spec:
            c = parse_color(self.ref(spec["color"]))
            if c is None:
                raise ValueError(f"bad colour in rule: {spec!r}")
            return fmt_color(c[0], c[1], c[2], float(spec.get("alpha", c[3])))
        val = self.ref(spec)
        c = parse_color(val)
        if c is None:
            return val
        a = c[3]
        if keep_alpha and orig is not None and orig[3] < 1:
            a = orig[3] * c[3]
        return fmt_color(c[0], c[1], c[2], a)

    def tint(self, c, t):
        h, l, s = to_hls(c)
        return from_hls(h, float(t.get("l", l)), s * float(t.get("s_mult", 1)), c[3])

    def ramp(self, c, p):
        h, l, s = to_hls(c)
        lo, hi = float(p["l_min"]), float(p["l_max"])
        return from_hls(h, lo + l * (hi - lo), s * float(p.get("s_mult", 1)), c[3])

    def walk_colors(self, v, fn):
        if isinstance(v, list):
            return (
                [v[0]] + [self.walk_colors(x, fn) for x in v[1:]]
                if v and isinstance(v[0], str)
                else [self.walk_colors(x, fn) for x in v]
            )
        c = parse_color(v)
        if c is None or c[3] == 0:
            return v
        return fn(c)

    def fallback_value(self, layer_type, prop, value):
        if prop in self.fb.get("skip_props", []):
            return value
        if prop == "text-halo-color" and "text-halo-color" in self.fb:
            spec = self.fb["text-halo-color"]
            return self.walk_colors(value, lambda c: self.color_value(spec, fmt_color(*c), True))
        if prop.startswith("text-"):
            spec = self.fb.get("text")
            if spec is None:
                return value
            return self.walk_colors(
                value,
                lambda c: self.tint(c, spec["tint"])
                if "tint" in spec
                else self.color_value(spec, fmt_color(*c), True),
            )
        key = {
            "fill": "fill",
            "background": "fill",
            "fill-extrusion": "fill",
            "line": "line",
            "circle": "circle",
        }.get(layer_type)
        if key is None or key not in self.fb:
            return value
        return self.walk_colors(value, lambda c: self.ramp(c, self.fb[key]))

    # -- matching --------------------------------------------------------------
    @staticmethod
    def rule_matches(rule, layer):
        m = rule.get("match", {})
        fields = {
            "id": layer.get("id", ""),
            "type": layer.get("type", ""),
            "source_layer": layer.get("source-layer", ""),
        }
        for k in ("id", "type", "source_layer"):
            if k in m and not re.search(m[k], fields[k] or ""):
                return False
        for prop, rx in (m.get("paint") or {}).items():
            c = parse_color((layer.get("paint") or {}).get(prop))
            if c is None or not re.search(rx, hex_key(c)):
                return False
        return True

    # -- per style ---------------------------------------------------------------
    def shadow(self, style: dict, service: dict, style_url: str | None, source_mode: str = "tiles"):
        style = copy.deepcopy(style)
        rules = service.get("rules", [])
        report = []

        for layer in style.get("layers", []):
            ltype = layer.get("type")
            matched = [r for r in rules if self.rule_matches(r, layer)]
            notes = [r.get("note", "?") for r in matched]
            if any(r.get("skip") for r in matched):
                report.append((layer.get("id"), layer.get("source-layer", ""), ltype, "|".join(notes), "skipped"))
                continue

            had_paint = "paint" in layer
            paint = layer.setdefault("paint", {})
            layout_changes = {}
            assign = {}
            for r in matched:
                ka = r.get("keep_alpha", True)
                for prop, spec in (r.get("paint") or {}).items():
                    if prop_ok(ltype, prop):
                        assign[prop] = (spec, ka)
                for prop, spec in (r.get("layout") or {}).items():
                    layout_changes[prop] = spec

            for prop, (spec, ka) in assign.items():
                orig = paint.get(prop)
                if spec is None:
                    paint.pop(prop, None)
                    continue
                if is_color_prop(prop):
                    oc = parse_color(orig)
                    if oc is not None and oc[3] == 0:
                        continue
                    if orig is None and isinstance(spec, dict) and "tint" in spec:
                        continue
                    paint[prop] = self.color_value(spec, orig, ka)
                else:
                    paint[prop] = self.ref(spec)

            fb_props = []
            for prop in list(paint.keys()):
                if prop in assign or not is_color_prop(prop):
                    continue
                new = self.fallback_value(ltype, prop, paint[prop])
                if new != paint[prop]:
                    paint[prop] = new
                    fb_props.append(prop)

            if not had_paint and not paint:
                del layer["paint"]

            if layout_changes:
                lay = layer.setdefault("layout", {})
                for prop, spec in layout_changes.items():
                    if spec is None:
                        lay.pop(prop, None)
                    else:
                        lay[prop] = self.ref(spec)

            report.append(
                (layer.get("id"), layer.get("source-layer", ""), ltype, "|".join(notes), ",".join(fb_props))
            )

        bg = service.get("background")
        if bg:
            style["layers"].insert(
                0,
                {
                    "id": "background",
                    "type": "background",
                    "paint": {"background-color": self.color_value(bg, None, False)},
                },
            )

        if not style_url:
            raise ValueError("absolutizing needs the service's style_url")
        absolutize(style, style_url, source_mode)
        return style, report


# ----------------------------------------------------------------------------
# paths: rewrite Esri-relative sprite/glyphs/sources into absolute, MapLibre-ready URLs
# ----------------------------------------------------------------------------
from urllib.parse import urljoin, urlsplit, urlunsplit


def _strip_query(u: str) -> str:
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def absolutize(style: dict, style_url: str, source_mode: str = "tiles") -> None:
    """Mutates style in place: sprite/glyphs -> absolute URLs, vector sources -> explicit
    {z}/{x}/{y}.pbf tile templates (source_mode='tiles', MapLibre-ready) or an absolute Esri
    `url` (source_mode='url', for ArcGIS JS/OpenLayers)."""
    base = _strip_query(style_url)
    for key in ("sprite", "glyphs"):
        v = style.get(key)
        if isinstance(v, str):
            style[key] = urljoin(base, v)
    for src in (style.get("sources") or {}).values():
        if "url" in src and isinstance(src["url"], str):
            abs_url = urljoin(base, src["url"])
            if not abs_url.endswith("/"):
                abs_url += "/"
            if source_mode == "tiles" and src.get("type") == "vector":
                src["tiles"] = [abs_url + "tile/{z}/{y}/{x}.pbf"]
                del src["url"]
            else:
                src["url"] = abs_url
        if "tiles" in src:
            src["tiles"] = [urljoin(base, t) for t in src["tiles"]]
