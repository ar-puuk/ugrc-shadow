# ugrc-styles

Alternate MapLibre styles for [UGRC](https://gis.utah.gov/)'s Lite vector basemap
(`VectorHillshade`, `LiteBase`, `LiteLabels`), for [MapLibre](https://maplibre.org/). This repo
holds more than one style, developed side by side:

- **shadow** — a dark restyling built from [Protomaps](https://protomaps.com/)' dark flavor.
- **sol** — a warm light restyling based on [CARTO](https://carto.com/)'s Voyager basemap colors,
  using UGRC's `Vector_Overlay` sprite (the colorful icon set built for their Hybrid basemap)
  in place of LiteBase/LiteLabels' own muted grayscale icons.

**[Try it live →](https://ar-puuk.github.io/ugrc-styles/)**
A browser-only visual editor for customizing any built-in theme (or your own uploaded style):

- Browse layers grouped by service and by the same groups UGRC's own layer ids encode (e.g.
  "PARKS & REC"), search/filter by id, and reorder layers within a service.
- Edit colors/opacity/numbers/enums/filters/zoom ranges, with a raw-JSON fallback for anything
  the visual editor doesn't cover. A property that's split across several zoom-band layers (common
  in UGRC's own data — e.g. one road class split into a dozen-plus copies) can be edited once and
  applied to every other layer that currently shares that exact value, instead of repeating the
  edit by hand.
- Click the inspect tool, then hover or click anywhere on the map to see which layer is drawing
  what's under the cursor, and jump straight to it in the editor.
- A "Compare against" picker in the header swipes your in-progress edit against any theme, UGRC's
  own live basemap, or your upload, with an address search box and a live coordinates readout on
  either map.
- Crash-recovery autosave, light/dark/system theme, and resizable side panels.
- Download either one combined style JSON or the 3 separate
  `VectorHillshade`/`LiteBase`/`LiteLabels` files matching how UGRC actually hosts these.

Nothing you do here feeds back into this repo's build — see
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
    colorpicker.js         # the shadcn/ui-style color popover, same reason
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

## I downloaded a style JSON from the editor — now what?

A style JSON isn't a picture of a map — it's a set of instructions ("draw roads this color, at
this width, starting at this zoom") that a map library reads and renders *live*, still pulling the
actual map data from UGRC's servers over the network. You need something that understands that
format to see anything.

**Fastest way to just look at it:** drop the file into
[Maputnik](https://maplibre.org/maputnik/), a free browser-based style editor — no install, no
code. If it complains about the tile source, that's the one UGRC-specific gotcha below; fix that
first and it'll load.

**To put it on your own web page**, you need [MapLibre GL
JS](https://maplibre.org/maplibre-gl-js/docs/) (free, open source, no server-side component) and
one small fixup first:

> **The one gotcha:** the downloaded style's vector source is shaped the way Esri's ArcGIS
> `VectorTileServer` publishes it (`"url": "https://tiles.arcgis.com/.../VectorTileServer/"`) —
> Esri's own tools resolve that automatically, but MapLibre GL JS doesn't, and will fail with
> `Failed to parse URL from tile/...`. Rewrite it into the `tiles` array MapLibre expects before
> handing the style to `maplibregl.Map`:
>
> ```js
> for (const [id, src] of Object.entries(style.sources)) {
>   if (src.type === "vector" && typeof src.url === "string") {
>     style.sources[id] = { ...src, tiles: [src.url + "tile/{z}/{y}/{x}.pbf"] };
>     delete style.sources[id].url;
>   }
> }
> ```
>
> (This is exactly what `toTilesSource()`/`prepareForRender()` in
> [`docs/assets/styles.js`](docs/assets/styles.js) do for the live editor above — copy that
> instead if you'd rather reuse tested code. One more minor wart from the same upstream data:
> the source's own `attribution` field is literally the placeholder text `"me"` — harmless, but
> worth overriding with your own `customAttribution` if you add MapLibre's attribution control.)

A complete, working page — save as `.html`, point `fetch()` at whichever file you downloaded, open
it in a browser:

```html
<!doctype html>
<html>
<head>
  <script src="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.js"></script>
  <link href="https://unpkg.com/maplibre-gl@5.24.0/dist/maplibre-gl.css" rel="stylesheet" />
  <style>body { margin: 0; } #map { position: absolute; inset: 0; }</style>
</head>
<body>
  <div id="map"></div>
  <script>
    fetch("./ugrc-lite-edited.json") // whatever you downloaded, next to this file
      .then((r) => r.json())
      .then((style) => {
        for (const [id, src] of Object.entries(style.sources)) {
          if (src.type === "vector" && typeof src.url === "string") {
            style.sources[id] = { ...src, tiles: [src.url + "tile/{z}/{y}/{x}.pbf"] };
            delete style.sources[id].url;
          }
        }
        new maplibregl.Map({ container: "map", style, center: [-111.891, 40.761], zoom: 10 });
      });
  </script>
</body>
</html>
```

**Combined vs. the 3 separate files:** unless you specifically need UGRC's own native
`VectorHillshade`/`LiteBase`/`LiteLabels` split (e.g. feeding a system that already expects that
exact shape), download the **combined** style — it's the single file the snippet above expects,
with nothing further to merge. The 3-file download reproduces UGRC's own per-service file shapes
exactly, which is only useful if something else consumes that shape directly; recombining
them into one usable style yourself means redoing the sprite-namespacing/source-merging the editor
already does internally (see `mergeStyles()` in `docs/assets/styles.js`) — reach for the combined
download instead unless you already know why you need the split one.

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
