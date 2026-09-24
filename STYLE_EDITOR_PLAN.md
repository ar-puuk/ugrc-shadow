# Plan: a Maputnik-style editor page for `docs/`

Status: proposal, not yet implemented. Scope is entirely `docs/` (the static demo site published
to GitHub Pages) — nothing here touches `src/`, `config/`, or the Python build pipeline. Themes
keep being generated exactly as they are today; this just adds a second page that lets a visitor
customize a copy of a style in the browser, compare it against other styles, and download the
result.

## 1. Goal

Add `docs/editor.html`: a browser-only visual style editor, in the same spirit as
[Maputnik](https://maplibre.org/maputnik/) and Mapbox Studio's style editor, scoped specifically
to UGRC's styles:

- Start from one of this repo's built-in templates — **Lite** (UGRC's live original), **Shadow**,
  **Sol**, or any future theme in `docs/themes.json` — or upload an arbitrary MapLibre style JSON.
- Edit layers visually: toggle visibility, change paint/layout properties (colors, opacity,
  widths, text), edit simple filters and zoom ranges, with a raw-JSON fallback for anything the
  visual editor doesn't cover.
- Download the edited style as a standalone style JSON.
- Compare: reuse the existing side-by-side slider so either side can be a built-in template, an
  uploaded style, or the style currently being edited — not just two fixed templates like today's
  `index.html`.

## 2. Prior art — what's borrowed, what isn't

**Maputnik** (reference for feature shape, not code — its React/Redux app isn't vendored):
layer list as a searchable/filterable tree, click-to-select a layer to open its property panel,
properties grouped into sections (Layout, Paint, Filter, Min/max zoom) with a typed input per GL
property (color swatch, number, enum dropdown, data-driven-expression fallback), a "layers changed
from source" indicator, import/export of the whole style JSON, and a raw-JSON tab per layer for
anything the form doesn't model.

**Mapbox Studio** (reference for polish, not architecture): grouping layers under collapsible
sections that mirror the *source* they came from, a live-updating swatch next to each color
property instead of a raw hex field, and zoom-range shown as a small histogram/slider rather than
two bare number inputs. Worth borrowing the visual language; its source-linking and publish-to-
account features don't apply here (no backend, no accounts).

**Why not just embed/vendor Maputnik itself** (per your steer): its property panel assumes a
"clean" Mapbox/MapLibre style. UGRC's generated styles are Esri VectorTileServer output re-shaped
for MapLibre — the `esri` source keeps Esri's `url` form instead of a `tiles` array (see
`vectorUrlSourceToTiles` in `docs/index.html`), sprites are per-service and get merged/namespaced
(`mergeStyles`), and a "theme" is really 3 Esri services stitched into one style. A generic
Maputnik either chokes on the raw per-service JSON or has no opinion about the merge step. Building
our own means the editor can bake in exactly the UGRC-specific plumbing `index.html` already has,
and skip everything Maputnik supports that we don't need.

## 3. Editing model: one merged view in the editor, exportable either combined or as UGRC's 3 files

`buildOriginalStyle()` / `buildThemeStyle()` in `docs/index.html` already fetch a template's 3
services (`VectorHillshade`, `LiteBase`, `LiteLabels`) and flatten them through `mergeStyles()`
into one namespaced MapLibre style (shared `esri`-family sources, a sprite array, deduped layer
ids). The editor's layer tree/map/property panel all operate on **that merged view** — one layer
list, one map, one set of property panels, regardless of whether 3 services went into it or a
visitor uploaded a single arbitrary style. That part of the original plan stands.

What changes: UGRC hosts, and per your note will keep hosting for the foreseeable future, three
separate style JSONs — and that's also this repo's own committed output shape
(`docs/<theme>/styles/UGRC_<Service>_<theme>.json`). Most people customizing "the UGRC style" for
their own map want those same three files back, not one merged blob — so export needs to go back
the other way for anything that started as one of our own templates. To make that possible,
`mergeStyles()` needs one addition: tag each merged layer with where it came from, e.g.
`layer.metadata["ugrc:service"] = name` — the GL spec explicitly allows an opaque `metadata` object
per layer for exactly this kind of app-level bookkeeping, and it round-trips through MapLibre
untouched. `buildThemeStyle()`/`buildOriginalStyle()` also need to retain each service's original,
un-namespaced `sprite`/`glyphs`/`sources` object after the merge call (already fetched, just
currently discarded once `mergeStyles()` returns).

Un-merging at export time (§8) is then: group the edited layers by `metadata["ugrc:service"]`, and
for each of the 3 services rebuild `{version 8, sprite, glyphs, sources, layers}` from that
service's retained original sprite/glyphs/source object, renaming each layer's `source` back from
its merged/namespaced form to the service's own original source key, and stripping any
`${service}:`-prefixed `icon-image` that `mergeStyles()` added for non-default sprites.

A layer the user adds from scratch (§7) has no `metadata["ugrc:service"]` yet — the "add layer"
flow asks which of the 3 services it belongs to (defaulting to whichever layer is currently
selected), the same choice Maputnik's own "add layer" dialog makes you pick a source for.

An **uploaded** arbitrary style that isn't one of our own templates carries no service split at
all — for that case only the combined single-file export applies (§8); "download 3 files" is only
offered when what's loaded traces back to a built-in template, or to a prior 3-file export
reloaded with its `metadata` intact.

## 4. Refactor first: share code between `index.html` and the new page

`docs/index.html`'s inline `<script>` already contains everything the editor needs to load a
style: `fetchJson`, `joinUrl`, `vectorUrlSourceToTiles`, `absolutize`, `resolveThemeStyle`,
`mergeStyles`, `buildOriginalStyle`, `buildThemeStyle`, `loadOptions`, and the `Dropdown` class.
Duplicating ~350 lines into a second page is the wrong move. Before writing any editor-specific
code:

1. Extract the style-loading functions into `docs/assets/styles.js` (ES module, no bundler —
   `<script type="module">`, matching the zero-build-step nature of this site).
2. Extract `Dropdown` into `docs/assets/dropdown.js`.
3. Update `index.html` to import both and keep working exactly as it does today (no visible
   behavior change — this step is pure refactor, verified by manually re-checking the compare
   demo).
4. Editor page imports the same two modules.

This keeps `index.html` and `editor.html` from drifting out of sync on how a template gets turned
into a loadable style.

## 5. Page layout

`docs/editor.html`, same dark/glass visual language as `index.html` (reuse `--accent`,
`--glass-bg`, `.glass`, `.dd-*` styles — worth also pulling shared CSS into
`docs/assets/base.css` during the refactor in §4).

```
┌─────────────────────────────────────────────────────────────┐
│ header: brand · "Start from" template/upload picker · [↓]   │  (↓ = download)
├───────────────┬───────────────────────────────────────────────┤
│ layer list     │                                               │
│ (search box +  │              MapLibre map                    │
│  tree grouped  │        (single map, or split via              │
│  by id path -  │         compare mode toggle)                  │
│  see §6)       │                                               │
│                ├───────────────────────────────────────────────┤
│                │ property panel for selected layer             │
│                │ (Layout / Paint / Filter / Zoom tabs)          │
└───────────────┴───────────────────────────────────────────────┘
```

Compare mode is a header toggle, not a separate page: off = single full-bleed map you're editing;
on = the existing `maplibre-gl-compare` slider, left/right pickers reused from `index.html`'s
pattern (§7) but with two extra entries prepended: **"Your upload"** and **"Current edit."**

## 6. Layer list

UGRC's generated layer ids are already slash-delimited pseudo-paths (e.g.
`Base/PARKS & REC/Cemeteries_Poly`, `Base/Utah/Utah/1`) — a free grouping hierarchy. Build a
collapsible tree from splitting `id` on `/`, rooted one level up by originating service
(`VectorHillshade` / `LiteBase` / `LiteLabels`, recoverable from which merged source each layer
points at). Each leaf row: visibility toggle (flips `layout.visibility` between `visible`/`none`),
a small type icon (fill/line/symbol/circle/raster), and a color swatch preview when the layer has
one dominant paint color. A text filter box above the tree (matches on id substring) — necessary
given `LiteBase` alone is ~10k lines / several hundred layers.

An uploaded arbitrary style won't have this slash-path convention — fall back to a flat
alphabetical list grouped only by `type` when ids don't contain `/`.

## 7. Property panel

Tabs per selected layer: **Paint**, **Layout**, **Filter**, **Zoom**. Render one input per
property actually present on the layer (don't offer every possible GL property — only what's
there, plus an "add property" affordance scoped to that layer's type). Typed inputs:

- Color (`fill-color`, `line-color`, `text-color`, …): swatch + hex field + separate alpha slider
  — native `<input type=color>` has no alpha channel, and these styles lean on `rgba(...)` (see
  `UGRC_LiteBase_shadow.json`'s `rgba(31,31,31,0.3)`), so alpha needs its own control, composed
  back into an `rgba()` string on change.
- Number (`line-width`, `*-opacity`, `text-size`, …): number input + range slider, clamped to that
  property's spec range.
- Enum (`line-cap`, `text-anchor`, `symbol-placement`, …): dropdown of the spec's valid values.
- String (`text-field`, `icon-image`): plain text input.
- **Anything else** (data-driven `["interpolate", ...]` / `["match", ...]` expressions, arrays):
  a raw-JSON textarea for that single property, parsed/validated on blur. No visual expression
  builder in v1 — flagged as a known gap below.

Filter tab: a simple builder for the `["==", "field", value]` / `["!=", ...]` shape these styles
actually use (single dropdown for operator, text input for field, text input for value), with a
raw-JSON textarea escape hatch for anything more complex (`all`/`any`/nested filters).

Zoom tab: `minzoom`/`maxzoom` as a two-handle range slider over 0–24.

A per-layer "reset to template" button (only enabled once that layer differs from the loaded
template) and a global "changed layers: N" counter in the header, both computed by diffing the
live style against the originally-loaded one.

## 8. Upload / download

- **Upload**: `<input type=file accept=".json">` (or drag-and-drop onto the map), `JSON.parse`,
  minimal shape validation (`version === 8`, `sources`, `layers` present), then loaded through the
  same code path as a template — skip `resolveThemeStyle`'s UGRC-specific relative-sprite handling
  for uploads (assume an uploaded style's sprite/glyphs are already absolute, since it isn't one of
  this repo's own outputs).
- **Download — two options, offered when applicable**:
  - **Three style JSONs (default/primary)**: `UGRC_VectorHillshade_<name>.json`,
    `UGRC_LiteBase_<name>.json`, `UGRC_LiteLabels_<name>.json`, re-split per §3. This is what most
    visitors customizing "the UGRC style" actually want — the same three files UGRC hosts and this
    repo already publishes, addable to a map exactly as the README already describes. Only offered
    when the loaded style traces back to a built-in template (or a reloaded 3-file export with its
    `metadata["ugrc:service"]` tags intact).
  - **Combined single style JSON (secondary)**: the merged style as one file, for anyone who wants
    one file instead of three, or who started from a single-file upload (in which case it's the
    only option — no service split to reconstruct).
  Each triggers a `JSON.stringify(style, null, 2)` `Blob` via a temporary `<a download>`; the
  3-file option just fires it three times in a row rather than needing a zip dependency (worth
  revisiting only if three separate browser download prompts prove annoying in testing).

## 9. Compare mode integration (per your answer in §2 of the review)

Extend the existing picker-option model (`loadOptions()` in `docs/assets/styles.js` after the
refactor) so both the editor's own "start from" picker and the compare sliders' left/right pickers
draw from one superset list:

- every entry from `docs/themes.json`, plus `original` ("Lite") — exactly as today
- `upload` — present only once a file has actually been loaded this session
- `current-edit` — present once the user has changed anything from the loaded template; always
  reflects the live in-progress style object, not a snapshot, so toggling into compare mode while
  mid-edit shows the edit as it stands

Left/right `Dropdown`s reuse `docs/assets/dropdown.js` unchanged.

## 10. Persistence

No backend, no account, no URL-encoded state (these merged styles run tens of thousands of
characters — too big for a shareable URL). The only real "save" is one of the file downloads in
§8 — closing the tab or navigating away without downloading discards the edits, by design (per
your framing: save as file(s), or discard). A `localStorage` autosave (debounced, keyed by which
template the session started from) is worth keeping purely as a crash/reload safety net so an
accidental tab close doesn't silently lose work — but it's a recovery convenience, not a save
mechanism, and never presented to the user as an alternative to actually downloading a file.

## 11. Stack / dependencies

No new build tooling — this site has none today and should keep it that way. Everything is a
`<script type="module">` ES module loaded straight by the browser, same CDN pins as `index.html`
(`maplibre-gl`, `maplibre-gl-compare`). No JSON-editor library (CodeMirror/Monaco) for the raw-JSON
fallback fields — plain `<textarea>` with `JSON.parse`/`stringify` round-tripping and a visible
parse-error message is enough for the few escape-hatch fields in §7, and keeps this dependency-free
like the rest of the site.

## 12. Known gaps / non-goals for v1

- No visual builder for `interpolate`/`match`/`step` expressions — raw-JSON textarea only.
- No sprite/icon editing (recoloring or replacing icon images) — sprites stay fixed per template.
- Re-splitting into 3 files is for *download*, not for feeding back into this repo's build —
  `config/themes/` works from `theme.json`/palette rules, not by hand-editing an output style, so
  a 3-file export still isn't a "contribute a new theme" pathway even though it's the same shape.
- No server-side sharing/short-links for an edited style.
- No `raster`/`hillshade`-specific property support beyond what `VectorHillshade`'s existing layers
  already use (its style has ~400 lines vs. LiteBase's ~10,700 — not the primary target).

## 13. Phased implementation

1. **Refactor** (§4): pull shared JS/CSS out of `index.html` into `docs/assets/`, verify the
   existing compare demo is pixel-identical in behavior. Also add the `metadata["ugrc:service"]`
   tagging and retained per-service sprite/glyphs/sources to `mergeStyles()`/`buildThemeStyle()`/
   `buildOriginalStyle()` here (§3) — an additive, behavior-preserving change `index.html` doesn't
   otherwise need. No editor code yet.
2. **Scaffold**: `editor.html` loads a template or upload, renders a single map, raw-JSON
   read-only view, and the combined single-file download (simplest export path end to end).
3. **Layer list** (§6): tree/list + search + visibility toggle + selection.
4. **Property panel** (§7): typed inputs for Paint/Layout, then Filter and Zoom tabs, then the
   raw-JSON fallback field and the per-layer/global "changed" diffing.
5. **3-file export** (§3/§8): the un-merge step and the "add layer → pick a service" flow —
   deferred until there's real layer data to test it against.
6. **Compare mode** (§9): slider toggle, extended option list including upload/current-edit.
7. **Polish**: `localStorage` crash-recovery autosave (§10), mobile layout, a11y pass (keyboard
   nav through the layer tree, labeled form controls), link the two pages from each other's header,
   README update pointing at the new page.

Each phase should be checked manually in a browser (serve `docs/` locally, e.g.
`python -m http.server` from that directory) before moving to the next — there's no test suite
covering `docs/`, and none is proposed here since this is UI-driven, not logic to unit test.
