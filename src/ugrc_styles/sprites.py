"""Reworks a UGRC sprite sheet (LiteLabels' highway shields, LiteBase's icons) to match a theme.

Every icon is a plain raster PNG (`"sdf": false`), so MapLibre's `icon-color` can't recolor
them - the pixels have to be rewritten directly. A theme picks one of two whole-sheet transforms
(its `sprite_transform` in theme.json):

- "invert": every opaque pixel gets its lightness flipped (l' = 1 - l) in HLS space, keeping hue
  and saturation, so e.g. the Interstate shield's red/blue chrome moves into shadow in place
  instead of shifting hue the way a literal RGB channel-invert would. Used by dark themes like
  "shadow", whose backdrop is much darker than the icons were originally baked for.
- "none": pixels pass through unchanged. Used by light-on-light themes like "sol", where Esri's
  original icon colors already read fine against the new (still light) backdrop and the brief is
  to restyle the map's colors, not its elements.

Either way, icon positions/sizes are untouched - only pixel colors move (or don't) - so the
original sprite.json's layout is reused as-is for both the 1x and 2x sheets.

A handful of icons need to match an exact palette color rather than following the sheet-wide
transform - e.g. LiteBase's railroad tie-mark icon and the "Railroads" line layer beside it are
both the identical gray in UGRC's original ("#B3AFAF" for each), so they need to land on the
same theme-appropriate gray too. The line gets there via the normal rule engine (@rail); the icon
can't, since icon-color is a no-op on a non-SDF icon - so `recolor` stamps it to @rail's literal
value directly instead of relying on the sheet-wide transform to happen to land on the same spot.
"""
from __future__ import annotations

import io

import requests
from PIL import Image

from ugrc_styles.colors import invert_lightness, parse_color
from ugrc_styles.fetch import fetch_bytes, fetch_json


def shadow_sprite_image(
    png_bytes: bytes,
    recolor_regions: list[tuple[int, int, int, int, tuple[int, int, int]]] | None = None,
    transform: str = "invert",
) -> bytes:
    """`recolor_regions` is a list of (x, y, width, height, target_rgb) boxes: every opaque
    pixel inside one is stamped to target_rgb (alpha kept) regardless of `transform`.

    `transform` is the whole-sheet treatment applied to every other opaque pixel: "invert" flips
    lightness (hue/saturation kept), "none" leaves pixels exactly as they are."""
    if transform not in ("invert", "none"):
        raise ValueError(f"unknown sprite transform: {transform!r}")

    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    pixels = img.load()
    w, h = img.size

    stamp = [[None] * w for _ in range(h)]
    for rx, ry, rw, rh, target in recolor_regions or []:
        for y in range(max(ry, 0), min(ry + rh, h)):
            for x in range(max(rx, 0), min(rx + rw, w)):
                stamp[y][x] = target

    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            target = stamp[y][x]
            if target is not None:
                pixels[x, y] = (target[0], target[1], target[2], a)
            elif transform == "invert":
                nr, ng, nb, na = invert_lightness((r, g, b, a / 255))
                pixels[x, y] = (round(nr), round(ng), round(nb), round(na * 255))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _regions_for(sprite_json: dict, recolor: dict[str, str]) -> list[tuple[int, int, int, int, tuple[int, int, int]]]:
    regions = []
    for icon_name, hex_color in recolor.items():
        box = sprite_json.get(icon_name)
        if box is None:
            continue
        c = parse_color(hex_color)
        if c is None:
            raise ValueError(f"bad recolor target for {icon_name!r}: {hex_color!r}")
        regions.append((box["x"], box["y"], box["width"], box["height"], (round(c[0]), round(c[1]), round(c[2]))))
    return regions


def _paste_icons_below(base_json: dict, base_png: bytes, extra_json: dict, extra_png: bytes, icon_names: list[str]) -> tuple[dict, bytes]:
    """Returns (new_json, new_png): `base` with `icon_names` copied in from `extra`, packed
    left-to-right in a new row beneath `base`'s existing icons. Both JSONs/PNGs must be at the
    same pixel density (both 1x, or both @2x) - the caller pairs them up."""
    base_img = Image.open(io.BytesIO(base_png)).convert("RGBA")
    extra_img = Image.open(io.BytesIO(extra_png)).convert("RGBA")
    bw, bh = base_img.size

    row_h = max((extra_json[name]["height"] for name in icon_names), default=0)
    row_w = sum(extra_json[name]["width"] for name in icon_names)
    canvas = Image.new("RGBA", (max(bw, row_w), bh + row_h), (0, 0, 0, 0))
    canvas.paste(base_img, (0, 0))

    new_json = dict(base_json)
    x = 0
    for name in icon_names:
        box = extra_json[name]
        icon_img = extra_img.crop((box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]))
        # no mask: a mask arg would use icon_img's own alpha to alpha-BLEND against the canvas
        # (which is fully transparent here anyway), corrupting semi-transparent edge pixels by
        # lerping their color toward transparent black instead of copying them through as-is.
        canvas.paste(icon_img, (x, bh))
        new_json[name] = {**box, "x": x, "y": bh}
        x += box["width"]

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    return new_json, out.getvalue()


def merge_sprites(base: dict, extra: dict, icon_names: list[str]) -> dict:
    """Returns a new sprite dict (same shape as shadow_sprite()'s return value) with `icon_names`
    copied into `base` from `extra` - for icons a theme's borrowed primary sprite doesn't have
    (see e.g. sol's theme.json), so they don't just vanish, without resorting to MapLibre's
    multi-sprite arrays (which docs/index.html's own merge step doesn't understand).

    `icon_names` must exist in extra["json"] (and extra["json@2x"], if base has a @2x sheet) - a
    KeyError means the assumption that extra's sprite has these icons no longer holds. Assumes
    none of `icon_names` already exist in base (true for every current borrow: the two sprites
    use disjoint naming schemes) - if one did, it would just be overwritten.
    """
    new_json, new_png = _paste_icons_below(base["json"], base["png"], extra["json"], extra["png"], icon_names)
    merged = {"json": new_json, "png": new_png, "json@2x": base["json@2x"], "png@2x": base["png@2x"]}
    if base["json@2x"] is not None and extra["json@2x"] is not None:
        merged["json@2x"], merged["png@2x"] = _paste_icons_below(
            base["json@2x"], base["png@2x"], extra["json@2x"], extra["png@2x"], icon_names
        )
    return merged


def shadow_sprite(
    sprite_base_url: str, recolor: dict[str, str] | None = None, transform: str = "invert"
) -> dict[str, bytes | dict]:
    """Fetch a sprite sheet (json + png, and @2x if present) live and rework its pixels.

    `recolor` maps an icon name (as it appears in sprite.json) to a literal hex color it should
    be stamped to exactly, regardless of `transform`. `transform` is the theme's whole-sheet
    treatment for every other icon - see shadow_sprite_image().

    Returns {"json": dict, "png": bytes, "json@2x": dict | None, "png@2x": bytes | None}.
    The json is unchanged except it's the same object handed back for convenience - only the
    PNGs are modified.
    """
    recolor = recolor or {}
    sprite_json = fetch_json(f"{sprite_base_url}.json")
    sprite_png = shadow_sprite_image(
        fetch_bytes(f"{sprite_base_url}.png"), _regions_for(sprite_json, recolor), transform
    )

    sprite_json_2x = sprite_png_2x = None
    try:
        sprite_json_2x = fetch_json(f"{sprite_base_url}@2x.json")
        sprite_png_2x = shadow_sprite_image(
            fetch_bytes(f"{sprite_base_url}@2x.png"), _regions_for(sprite_json_2x, recolor), transform
        )
    except requests.RequestException:
        pass  # no @2x sheet published - fine, 1x is required, 2x is a bonus

    return {
        "json": sprite_json,
        "png": sprite_png,
        "json@2x": sprite_json_2x,
        "png@2x": sprite_png_2x,
    }
