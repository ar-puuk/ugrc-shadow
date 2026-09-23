# ugrc-shadow

A dark-mode restyling of [UGRC](https://gis.utah.gov/)'s Lite vector basemap
(`VectorHillshade`, `LiteBase`, `LiteLabels`) for [MapLibre](https://maplibre.org/).

**[Live compare demo →](https://pukar-bhandari.github.io/ugrc-shadow/)** <!-- update once Pages is live -->

## What this is

UGRC publishes three public Esri vector-tile services that together make up their "Lite"
basemap. This tool fetches all three **live** and rewrites their `paint` colors against a
dark palette, producing three standalone, MapLibre-ready dark style JSONs — plus a darkened
version of the highway-shield sprite icons, which (being raster PNGs) can't be recolored
through paint properties alone.

The demo page swipes between UGRC's current Lite basemap and this dark version, both rendered
live in [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/).

## Where the colors come from

Most of the palette isn't "inspired by" [Protomaps](https://protomaps.com/)'s dark theme in a
loose sense — it's the literal color tokens `@protomaps/basemaps`' `namedFlavor("dark")`
returns, fetched live at build time (see [`src/ugrc_shadow/palette.py`](src/ugrc_shadow/palette.py)).
A handful of additional tokens UGRC's layers need that Protomaps has no equivalent for
(hillshade shading, road-class grays, trails, transit, etc.) live in
[`config/palette_extra.json`](config/palette_extra.json).

Similarly, UGRC's own three style definitions are never vendored into this repo — every build
fetches them fresh from UGRC's live ArcGIS endpoints (see [`src/ugrc_shadow/fetch.py`](src/ugrc_shadow/fetch.py)).
Only the *generated dark output* is committed, specifically so it can be used directly without
running any code (see below).

## Using the output directly

`docs/styles/UGRC_{VectorHillshade,LiteBase,LiteLabels}_dark.json` and `docs/sprites/shields-dark.*`
are committed, ready-to-use artifacts — standalone MapLibre style JSON and sprite sheet, with
absolute tile/sprite/glyph URLs already filled in. Add all three style layers to a MapLibre map
the same way you'd add UGRC's originals; no light/original equivalent is published here, since
UGRC's own live services are already directly usable for that.

## Regenerating

```bash
uv sync
uv run ugrc-shadow                       # writes docs/styles/*.json + docs/sprites/*
uv run ugrc-shadow --base-url https://pukar-bhandari.github.io/ugrc-shadow  # absolute sprite URL for publishing
```

Run `uv run pytest` for the unit tests (color math + rule matching).

## Credits

- Basemap data and tiles: [UGRC](https://gis.utah.gov/) (Utah AGRC), served via Esri
  ArcGIS Online `VectorTileServer` endpoints.
- Dark palette: [Protomaps](https://protomaps.com/) `@protomaps/basemaps`
  (BSD-3-Clause), via its `namedFlavor("dark")`.

## License

MIT — see [LICENSE](LICENSE). The Protomaps palette this derives from is BSD-3-Clause
licensed; see the credits above.
