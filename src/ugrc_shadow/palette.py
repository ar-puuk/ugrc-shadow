"""The dark palette: fetched live from Protomaps' actual dark flavor, extended with a small
set of UGRC-specific tokens Protomaps has no equivalent for.

Most of this tool's colors are not "inspired by" Protomaps in some vague sense - they are the
literal values `@protomaps/basemaps`' `namedFlavor("dark")` returns for its own dark theme
(verified by diffing against the flavor dump; see PROTOMAPS_KEY_MAP below for exactly which
keys line up). Fetching it live, every run, means this pipeline's connection to that source
stays explicit rather than silently drifting from a copy frozen at whatever moment someone
last eyeballed it.
"""
from __future__ import annotations

import json
from pathlib import Path

from py_mini_racer import MiniRacer

from ugrc_shadow.fetch import fetch_text

PROTOMAPS_VERSION = "5.7.2"
PROTOMAPS_BUNDLE_URL = f"https://cdn.jsdelivr.net/npm/@protomaps/basemaps@{PROTOMAPS_VERSION}/dist/basemaps.js"
PROTOMAPS_FLAVOR = "dark"

# our palette key -> the exact key @protomaps/basemaps exposes it under in namedFlavor("dark")
PROTOMAPS_KEY_MAP: dict[str, str] = {
    "background": "background",
    "earth": "earth",
    "park": "park_b",
    "water": "water",
    "boundary": "boundaries",
    "road_highway": "highway",
    "road_major": "major",
    "road_minor": "minor_b",
    "label_minor": "roads_label_minor",
    "label": "roads_label_major",
    "label_major": "city_label",
    "label_region": "country_label",
    "label_water": "ocean_label",
    "halo": "earth",
    "halo_water": "water",
    "buildings": "buildings",
    "hs_base": "earth",  # hillshade's neutral tone = the land fill it sits on
}


def fetch_protomaps_flavor(
    flavor: str = PROTOMAPS_FLAVOR, bundle_url: str = PROTOMAPS_BUNDLE_URL
) -> dict:
    """Live-fetch the pinned @protomaps/basemaps UMD bundle and evaluate
    `basemaps.namedFlavor(flavor)` in an embedded V8 context (PyMiniRacer - the Python analog
    of the R reference script's use of the {V8} package for the same purpose)."""
    bundle = fetch_text(bundle_url)
    ctx = MiniRacer()
    ctx.eval(bundle)
    result = ctx.eval(f"JSON.stringify(basemaps.namedFlavor({flavor!r}))")
    return json.loads(result)


def build_palette(extra_path: Path) -> dict[str, str]:
    """The final palette: live Protomaps tokens (renamed to our schema) + our own extras."""
    flavor_colors = fetch_protomaps_flavor()
    palette = {}
    for our_key, flavor_key in PROTOMAPS_KEY_MAP.items():
        if flavor_key not in flavor_colors:
            raise KeyError(
                f"Protomaps flavor no longer has {flavor_key!r} (mapped from {our_key!r}) - "
                "the pinned @protomaps/basemaps version may need updating."
            )
        palette[our_key] = flavor_colors[flavor_key]

    extra = json.loads(Path(extra_path).read_text(encoding="utf-8"))
    extra.pop("_about", None)
    overlap = set(palette) & set(extra)
    if overlap:
        raise ValueError(f"palette_extra.json redefines live Protomaps keys: {sorted(overlap)}")
    palette.update(extra)
    return palette
