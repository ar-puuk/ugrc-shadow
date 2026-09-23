"""Darkens the LiteLabels highway-shield sprite sheet.

The shield icons (Interstate/US Highway/State Highway) are plain raster PNGs (`"sdf": false`),
so MapLibre's `icon-color` can't recolor them - the pixels have to be rewritten directly. Every
opaque pixel gets its lightness flipped (l' = 1 - l) in HLS space, keeping hue and saturation,
so the Interstate shield's red/blue chrome darkens in place instead of shifting hue the way a
literal RGB channel-invert would. Icon positions/sizes are untouched - only pixel colors move -
so the original sprite.json's layout is reused as-is for both the 1x and 2x sheets.
"""
from __future__ import annotations

import io

import requests
from PIL import Image

from ugrc_shadow.colors import invert_lightness
from ugrc_shadow.fetch import fetch_bytes, fetch_json


def darken_sprite_image(png_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            nr, ng, nb, na = invert_lightness((r, g, b, a / 255))
            pixels[x, y] = (round(nr), round(ng), round(nb), round(na * 255))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def darken_sprite(sprite_base_url: str) -> dict[str, bytes | dict]:
    """Fetch a sprite sheet (json + png, and @2x if present) live and darken its pixels.

    Returns {"json": dict, "png": bytes, "json@2x": dict | None, "png@2x": bytes | None}.
    The json is unchanged except it's the same object handed back for convenience - only the
    PNGs are modified.
    """
    sprite_json = fetch_json(f"{sprite_base_url}.json")
    sprite_png = darken_sprite_image(fetch_bytes(f"{sprite_base_url}.png"))

    sprite_json_2x = sprite_png_2x = None
    try:
        sprite_json_2x = fetch_json(f"{sprite_base_url}@2x.json")
        sprite_png_2x = darken_sprite_image(fetch_bytes(f"{sprite_base_url}@2x.png"))
    except requests.RequestException:
        pass  # no @2x sheet published - fine, 1x is required, 2x is a bonus

    return {
        "json": sprite_json,
        "png": sprite_png,
        "json@2x": sprite_json_2x,
        "png@2x": sprite_png_2x,
    }
