# ugrc-styles

Alternate MapLibre styles for [UGRC](https://gis.utah.gov/)'s Lite vector basemap
(`VectorHillshade`, `LiteBase`, `LiteLabels`), for [MapLibre](https://maplibre.org/). This repo
holds more than one style, developed side by side:

- **shadow** — a dark restyling built from [Protomaps](https://protomaps.com/)' dark flavor.
- **sol** — a warm light restyling based on [CARTO](https://carto.com/)'s Voyager basemap colors,
  using UGRC's `Vector_Overlay` sprite (the colorful icon set built for their Hybrid basemap)
  in place of LiteBase/LiteLabels' own muted grayscale icons.

**[Try it live →](https://ar-puuk.github.io/ugrc-styles/)** <!-- update once Pages is live -->
A browser-only visual editor for customizing any built-in theme (or your own uploaded style):
browse layers grouped by service and by the same groups UGRC's own layer ids encode (e.g.
"PARKS & REC"), edit colors/opacity/numbers/enums/filters/zoom ranges, reorder layers within a
service, and download either one combined style JSON or the 3 separate
`VectorHillshade`/`LiteBase`/`LiteLabels` files matching how UGRC actually hosts these. A
A "Compare against" picker in the header swipes your in-progress edit against any theme, UGRC's own
live basemap, or your upload. Nothing you do here feeds back into this repo's build — see
[`STYLE_EDITOR_PLAN.md`](STYLE_EDITOR_PLAN.md) for the design.

## What this is

UGRC publishes three public Esri vector-tile services that together make up their "Lite"
basemap. For each theme, this tool fetches all three **live** and rewrites their `paint` colors
against that theme's own palette, producing three standalone, MapLibre-ready style JSONs per
theme — plus a reworked copy of the highway-shield and base-icon sprite icons, which (being
raster PNGs) can't be recolored through paint properties alone.

## Repo layout

```
config/
  services.json           # UGRC's 3 live endpoints - shared by every theme
  themes/
    <theme>/
      theme.json           # palette source + sprite transform + which sprites to rework (optionally from a different sprite sheet, with an icon-name remap)
      fallback.json         # how unmatched color properties are treated
      palette_extra.json    # this theme's own tokens with no equivalent in its live source
      services/
        LiteBase.json        # this theme's rules + background for one UGRC service
        LiteLabels.json
        VectorHillshade.json

docs/
  index.html               # the editor + compare demo - reads themes.json, no per-theme changes
  assets/
    styles.js              # style loading/merging/splitting, split out of index.html's own script
    dropdown.js            # the custom picker combobox, same reason
  themes.json              # generated: theme labels + where each one's style JSONs live
  <theme>/
    styles/UGRC_<Service>_<theme>.json
    sprites/{base-icons,shields}-<theme>.*
```

Adding a new theme means adding a `config/themes/<name>/` directory (see "Adding a theme"
below) — nothing under `src/` or `docs/` needs to change.

## Where the colors come from

Each theme's palette is built from its own **live** upstream source, resolved fresh at build
time (see [`src/ugrc_styles/palette.py`](src/ugrc_styles/palette.py)) plus a small set of
theme-specific tokens that source has no equivalent for
(`config/themes/<theme>/palette_extra.json`):

- **shadow** uses the literal color tokens `@protomaps/basemaps`' `namedFlavor("dark")` returns.
- **sol** uses colors read directly out of CARTO's public Voyager GL style JSON.

Similarly, UGRC's own three style definitions are never vendored into this repo — every build
fetches them fresh from UGRC's live ArcGIS endpoints (see
[`src/ugrc_styles/fetch.py`](src/ugrc_styles/fetch.py)). Only the *generated* style output is
committed, specifically so it can be used directly without running any code (see below).

## Using the output directly

`docs/<theme>/styles/UGRC_{VectorHillshade,LiteBase,LiteLabels}_<theme>.json` and
`docs/<theme>/sprites/{base-icons,shields}-<theme>.*` are committed, ready-to-use artifacts —
standalone MapLibre style JSON and sprite sheets, with absolute tile/sprite/glyph URLs already
filled in. Add all three style layers to a MapLibre map the same way you'd add UGRC's originals;
no light/original equivalent is published here, since UGRC's own live services are already
directly usable for that.

## Regenerating

```bash
uv sync
uv run ugrc-styles                                  # every theme -> docs/<theme>/{styles,sprites} + docs/themes.json
uv run ugrc-styles --theme shadow                    # just one theme (repeat --theme for more than one)
uv run ugrc-styles --base-url https://ar-puuk.github.io/ugrc-styles  # absolute sprite URLs for publishing
```

Run `uv run pytest` for the unit tests (color math, rule matching, config/palette plumbing).

## Adding a theme

1. `config/themes/<name>/theme.json` — label/description, a `palette_source` (currently
   `{"type": "protomaps", "flavor": ..., "version": ...}` or `{"type": "carto", "style_url": ...}`
   — see [`src/ugrc_styles/palette.py`](src/ugrc_styles/palette.py) to add another source kind),
   a `sprite_transform` (`"invert"` for a dark theme, `"none"` for a light-on-light one), and
   which services' sprites need reworking (usually `LiteBase` and `LiteLabels`, plus any exact
   `recolor` overrides an icon needs).
2. `config/themes/<name>/fallback.json` — the lightness band unmatched fill/line/circle colors
   get compressed into, and the tint unmatched text gets.
3. `config/themes/<name>/palette_extra.json` — tokens with no equivalent in the theme's live
   source (see the file's own `_about` for the discipline: nothing here may duplicate a value
   the live source already provides).
4. `config/themes/<name>/services/{LiteBase,LiteLabels,VectorHillshade}.json` — the actual
   `@token`-driven rules per source-layer. Usually ported from an existing theme's rules with
   the palette keys re-pointed at values that suit the new theme.
5. `uv run ugrc-styles --theme <name>` and eyeball the result in `docs/index.html` locally.

## Credits

- Basemap data and tiles: [UGRC](https://gis.utah.gov/) (Utah AGRC), served via Esri
  ArcGIS Online `VectorTileServer` endpoints.
- Shadow palette: [Protomaps](https://protomaps.com/) `@protomaps/basemaps`
  (BSD-3-Clause), via its `namedFlavor("dark")`.
- Sol palette: [CARTO](https://carto.com/)'s Voyager basemap style.

## License

MIT — see [LICENSE](LICENSE). The Protomaps palette shadow derives from is BSD-3-Clause
licensed; see the credits above.
