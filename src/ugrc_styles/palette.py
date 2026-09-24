"""Each theme's base palette: fetched live from that theme's own upstream source, extended with
a small set of theme-specific tokens that source has no equivalent for.

'shadow' is built from the literal color tokens `@protomaps/basemaps`' `namedFlavor("dark")`
returns for its own dark theme (verified by diffing against the flavor dump; see
PROTOMAPS_KEY_MAP below for exactly which keys line up). 'sol' is built the same way from CARTO's
public Voyager GL style JSON (see CARTO_KEY_MAP). Fetching live, every run, means each theme's
connection to its source stays explicit rather than silently drifting from a copy frozen at
whatever moment someone last eyeballed it.
"""
from __future__ import annotations

import json
from pathlib import Path

from py_mini_racer import MiniRacer

from ugrc_styles.fetch import fetch_json, fetch_text

# -- protomaps -----------------------------------------------------------------------------

PROTOMAPS_BUNDLE_URL = "https://cdn.jsdelivr.net/npm/@protomaps/basemaps@{version}/dist/basemaps.js"

# our palette key -> the exact key @protomaps/basemaps exposes it under in namedFlavor(flavor)
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


def _fetch_protomaps_flavor(flavor: str, version: str) -> dict:
    """Live-fetch the pinned @protomaps/basemaps UMD bundle and evaluate
    `basemaps.namedFlavor(flavor)` in an embedded V8 context (PyMiniRacer - the Python analog
    of the R reference script's use of the {V8} package for the same purpose)."""
    bundle = fetch_text(PROTOMAPS_BUNDLE_URL.format(version=version))
    ctx = MiniRacer()
    ctx.eval(bundle)
    result = ctx.eval(f"JSON.stringify(basemaps.namedFlavor({flavor!r}))")
    return json.loads(result)


def _protomaps_palette(flavor: str, version: str) -> dict[str, str]:
    flavor_colors = _fetch_protomaps_flavor(flavor, version)
    palette = {}
    for our_key, flavor_key in PROTOMAPS_KEY_MAP.items():
        if flavor_key not in flavor_colors:
            raise KeyError(
                f"Protomaps flavor no longer has {flavor_key!r} (mapped from {our_key!r}) - "
                "the pinned @protomaps/basemaps version may need updating."
            )
        palette[our_key] = flavor_colors[flavor_key]
    return palette


# -- carto -----------------------------------------------------------------------------------

# our palette key -> (layer id, paint property) to read it from in a CARTO GL style.json
CARTO_KEY_MAP: dict[str, tuple[str, str]] = {
    "background": ("background", "background-color"),
    "earth": ("background", "background-color"),
    "park": ("park_national_park", "fill-color"),
    "water": ("water", "fill-color"),
    "boundary": ("boundary_county", "line-color"),
    "road_highway": ("road_mot_case_noramp", "line-color"),
    "road_major": ("road_pri_case_noramp", "line-color"),
    "road_minor": ("road_minor_case", "line-color"),
    "label_minor": ("roadname_minor", "text-color"),
    "label": ("roadname_pri", "text-color"),
    "label_major": ("place_city_r6", "text-color"),
    "label_region": ("place_state", "text-color"),
    "label_water": ("watername_lake", "text-color"),
    "halo": ("background", "background-color"),
    "halo_water": ("watername_ocean", "text-halo-color"),
    "buildings": ("building-top", "fill-color"),
    "hs_base": ("background", "background-color"),
}


def _carto_layer_color(style: dict, layer_id: str, prop: str) -> str:
    layer = next((ly for ly in style.get("layers", []) if ly.get("id") == layer_id), None)
    if layer is None:
        raise KeyError(f"CARTO style has no layer {layer_id!r}")
    value = (layer.get("paint") or {}).get(prop)
    if value is None:
        raise KeyError(f"CARTO layer {layer_id!r} has no paint property {prop!r}")
    if isinstance(value, str):
        return value
    if isinstance(value, dict) and "stops" in value:
        # a zoom-interpolated ramp: take the highest-zoom stop, i.e. the color it settles on
        # once you're zoomed in enough to actually see the feature clearly.
        return value["stops"][-1][1]
    raise ValueError(f"unsupported color value for {layer_id}.{prop}: {value!r}")


def _carto_palette(style_url: str) -> dict[str, str]:
    style = fetch_json(style_url)
    return {our_key: _carto_layer_color(style, layer_id, prop) for our_key, (layer_id, prop) in CARTO_KEY_MAP.items()}


# -- entry point -----------------------------------------------------------------------------

_SOURCES = {
    "protomaps": lambda src: _protomaps_palette(src.get("flavor", "dark"), src["version"]),
    "carto": lambda src: _carto_palette(src["style_url"]),
}


def build_palette(source: dict, extra_path: Path) -> dict[str, str]:
    """A theme's final palette: its live upstream tokens (renamed to our schema) + its own
    theme-specific extras (config/themes/<name>/palette_extra.json)."""
    kind = source["type"]
    if kind not in _SOURCES:
        raise ValueError(f"unknown palette source type: {kind!r} (expected one of {sorted(_SOURCES)})")
    palette = _SOURCES[kind](source)

    extra = json.loads(Path(extra_path).read_text(encoding="utf-8"))
    extra.pop("_about", None)
    overlap = set(palette) & set(extra)
    if overlap:
        raise ValueError(f"palette_extra.json redefines live upstream keys: {sorted(overlap)}")
    palette.update(extra)
    return palette
