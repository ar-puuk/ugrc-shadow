"use strict";

// Shared between docs/index.html (compare demo) and docs/editor.html (style editor): fetching
// UGRC's live services or a committed theme's style JSONs, absolutizing their URLs, and merging
// the 3 per-service styles into one MapLibre-ready style. See STYLE_EDITOR_PLAN.md §3-4.

// UGRC's 3 original services, fetched live (never snapshotted - see README).
export const ORIGINAL_SERVICE_URLS = {
  VectorHillshade: "https://tiles.arcgis.com/tiles/99lidPhWCzftIe9K/arcgis/rest/services/VectorHillshade/VectorTileServer/resources/styles/root.json",
  LiteBase:        "https://tiles.arcgis.com/tiles/99lidPhWCzftIe9K/arcgis/rest/services/LiteBase/VectorTileServer/resources/styles/root.json",
  LiteLabels:      "https://tiles.arcgis.com/tiles/99lidPhWCzftIe9K/arcgis/rest/services/LiteLabels/VectorTileServer/resources/styles/root.json",
};
export const ORIGINAL_KEY = "original";

export function withFormat(url) {
  return url.includes("f=") ? url : url + (url.includes("?") ? "&" : "?") + "f=json";
}

export async function fetchJson(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} fetching ${url}`);
  return resp.json();
}

/** The URL API percent-encodes "{" and "}" (e.g. glyphs' {fontstack}/{range} template),
 * which MapLibre then fails to recognize as tokens. Python's urljoin doesn't have this
 * problem (it does plain string joining, no re-encoding pass) - undo it here to match. */
export function joinUrl(base, rel) {
  return new URL(rel, base).href.replace(/%7B/g, "{").replace(/%7D/g, "}");
}

/** JS port of src/ugrc_styles/engine.py's absolutize(): rewrite Esri-relative sprite/glyphs/
 * source paths into absolute URLs. Mutates `style` in place. Needed for "original", whose
 * sprite/glyphs/source paths come straight from UGRC's still-Esri-relative root.json.
 *
 * Deliberately keeps a vector source's `url` in Esri's own shape (a VectorTileServer root, not a
 * MapLibre `tiles` array) rather than converting it here - both UGRC's live styles and this repo's
 * committed theme styles keep that shape (see source_mode="url" in src/ugrc_styles/engine.py), and
 * it's what an exported/downloaded style should preserve too (§3 of STYLE_EDITOR_PLAN.md). The
 * conversion MapLibre GL JS actually needs to render a source's `url` as TileJSON happens only in
 * toTilesSource(), applied to a throwaway copy right before merging (mergeStyles below) - never to
 * the retained original. */
export function absolutize(style, styleUrl) {
  const base = styleUrl.split(/[?#]/)[0];
  for (const key of ["sprite", "glyphs"]) {
    if (typeof style[key] === "string") style[key] = joinUrl(base, style[key]);
  }
  for (const src of Object.values(style.sources || {})) {
    if (typeof src.url === "string") {
      let absUrl = joinUrl(base, src.url);
      if (!absUrl.endsWith("/")) absUrl += "/";
      src.url = absUrl;
    }
    if (Array.isArray(src.tiles)) {
      src.tiles = src.tiles.map((t) => joinUrl(base, t));
    }
  }
}

/** A committed theme style's glyphs are already absolute (the Python build always absolutizes
 * that regardless of source_mode), but `sprite` is deliberately left relative (e.g.
 * "../sprites/base-icons-shadow"), written relative to the style JSON's OWN file location
 * (docs/<theme>/styles/X.json - so "../sprites/" lands back in docs/<theme>/sprites/). That
 * assumption only holds if something resolves it against the fetched file's URL: this code fetches
 * the JSON as plain data and hands MapLibre the resulting object (not a URL string), so MapLibre
 * has no idea where it came from and would instead resolve a relative sprite URL against the
 * *page's* location - one level too high, breaking every icon. So it's resolved by hand here,
 * against `styleUrl` (the style JSON's own absolute URL). Already-absolute sprite URLs (a build run
 * with --base-url) pass through unchanged, since `new URL(absolute, base)` ignores `base`. */
export function resolveThemeStyle(style, styleUrl) {
  if (typeof style.sprite === "string") {
    style.sprite = joinUrl(styleUrl, style.sprite);
  }
  for (const src of Object.values(style.sources || {})) {
    if (typeof src.url === "string") {
      src.url = src.url.endsWith("/") ? src.url : src.url + "/";
    }
  }
}

/** Esri's VectorTileServer root's own tile template is relative ("tile/{z}/{y}/{x}.pbf"), which
 * ArcGIS's own runtime resolves but MapLibre GL JS does not when it fetches a source's `url` as
 * TileJSON - it errors with "Failed to parse URL from tile/...". Returns a NEW source object in
 * MapLibre's `tiles`-array shape for rendering; never mutates `src`, so the Esri-shaped original
 * (as fetched/absolutized) stays intact for later re-export (splitMergedStyle below). `src.url`
 * must already be absolute with a trailing slash (guaranteed by absolutize/resolveThemeStyle). */
function toTilesSource(src) {
  if (src.type !== "vector" || typeof src.url !== "string") return src;
  const { url, ...rest } = src;
  return { ...rest, tiles: [url + "tile/{z}/{y}/{x}.pbf"] };
}

/** Deep-clones `style` and converts any vector source still in Esri's `url` shape into MapLibre's
 * `tiles` array shape (see toTilesSource above), leaving everything else untouched. For rendering
 * an uploaded style that might itself be one of this repo's own Esri-shaped exports re-uploaded
 * as-is - a plain MapLibre-native style (already a `tiles` array, or a non-vector source) passes
 * through unchanged. Never mutates `style`. */
export function prepareForRender(style) {
  const clone = JSON.parse(JSON.stringify(style));
  for (const [key, src] of Object.entries(clone.sources || {})) {
    clone.sources[key] = toTilesSource(src);
  }
  return clone;
}

/** JS port of the original R reference script's ugrc_merge_styles(): combine several named styles
 * (each with their own "esri" source) into one MapLibre style, namespacing sources and sprites so
 * they can coexist, and dedup layer ids. List order (Object.keys order) = bottom -> top.
 *
 * Also tags every merged layer with `metadata["ugrc:service"]` (which of `namedStyles` it came
 * from) and `metadata["ugrc:originalId"]` (its id before dedup-suffixing) - MapLibre's spec allows
 * an opaque per-layer `metadata` object for exactly this kind of app bookkeeping, and it round-trips
 * through the map untouched. Returns `{ style, serviceOriginals }`: `style` is the merged,
 * render-ready output (same shape this function always returned); `serviceOriginals` retains each
 * input service's own un-namespaced sprite/glyphs/sources plus the namespacing it was given, which
 * splitMergedStyle() uses to un-merge an edited style back into UGRC's native 3 files. */
export function mergeStyles(namedStyles, { glyphsFrom } = {}) {
  const names = Object.keys(namedStyles);
  const defaultSprite = names.includes(glyphsFrom) ? glyphsFrom : names[names.length - 1];

  const sources = {};
  const layers = [];
  const sprites = [];
  const idCounts = new Map();
  const serviceOriginals = {};

  for (const name of names) {
    const st = namedStyles[name];
    const srcNames = Object.keys(st.sources || {});
    const srcMap = {};
    for (const s of srcNames) {
      srcMap[s] = srcNames.length === 1 ? name : `${name}_${s}`;
      sources[srcMap[s]] = toTilesSource(st.sources[s]);
    }
    const isDefault = name === defaultSprite;
    if (st.sprite) sprites.push({ id: isDefault ? "default" : name, url: st.sprite });

    serviceOriginals[name] = {
      sprite: st.sprite,
      glyphs: st.glyphs,
      sources: st.sources, // Esri-shaped, absolute - matches the committed/hosted file format
      sourceKeyMap: srcMap, // original source name -> merged/namespaced source name
      isDefault,
    };

    for (const ly of st.layers || []) {
      const copy = JSON.parse(JSON.stringify(ly));
      const originalId = copy.id;
      if (copy.source) copy.source = srcMap[copy.source];
      const icon = copy.layout && copy.layout["icon-image"];
      if (!isDefault && typeof icon === "string" && icon) {
        copy.layout["icon-image"] = `${name}:${icon}`;
      }
      const n = idCounts.get(copy.id) || 0;
      idCounts.set(copy.id, n + 1);
      if (n > 0) copy.id = `${copy.id}__${n}`;
      copy.metadata = { ...(copy.metadata || {}), "ugrc:service": name, "ugrc:originalId": originalId };
      layers.push(copy);
    }
  }

  sprites.sort((a, b) => (a.id === "default" ? -1 : 1) - (b.id === "default" ? -1 : 1));

  const style = {
    version: 8,
    name: "UGRC merged",
    sprite: sprites,
    glyphs: namedStyles[defaultSprite].glyphs,
    sources,
    layers,
  };
  return { style, serviceOriginals };
}

/** The inverse of mergeStyles: given a (possibly edited) merged style's `layers` array and the
 * `serviceOriginals` mergeStyles produced for it, rebuild each originating service's own standalone
 * style JSON - the same {version, sprite, glyphs, sources, layers} shape UGRC hosts and this repo
 * already publishes at docs/<theme>/styles/UGRC_<Service>_<theme>.json. Layers whose
 * metadata["ugrc:service"] doesn't match `serviceOriginals` (e.g. a layer added by hand with no
 * service assigned yet) are silently omitted - callers should assign a service before export
 * (STYLE_EDITOR_PLAN.md §3). Returns null if `serviceOriginals` is falsy (nothing to split - an
 * uploaded style with no service origins has only the combined single-file export available). */
export function splitMergedStyle(mergedLayers, serviceOriginals) {
  if (!serviceOriginals) return null;
  const result = {};
  for (const [service, orig] of Object.entries(serviceOriginals)) {
    const reverseSourceMap = {}; // merged/namespaced name -> original name
    for (const [origName, mergedName] of Object.entries(orig.sourceKeyMap)) {
      reverseSourceMap[mergedName] = origName;
    }
    const layers = [];
    for (const ly of mergedLayers) {
      if (!ly.metadata || ly.metadata["ugrc:service"] !== service) continue;
      const copy = JSON.parse(JSON.stringify(ly));
      if (copy.source && reverseSourceMap[copy.source] !== undefined) {
        copy.source = reverseSourceMap[copy.source];
      }
      if (!orig.isDefault && copy.layout && typeof copy.layout["icon-image"] === "string") {
        const prefix = `${service}:`;
        if (copy.layout["icon-image"].startsWith(prefix)) {
          copy.layout["icon-image"] = copy.layout["icon-image"].slice(prefix.length);
        }
      }
      if (copy.metadata) {
        if (copy.metadata["ugrc:originalId"] != null) copy.id = copy.metadata["ugrc:originalId"];
        delete copy.metadata["ugrc:service"];
        delete copy.metadata["ugrc:originalId"];
        if (Object.keys(copy.metadata).length === 0) delete copy.metadata;
      }
      layers.push(copy);
    }
    result[service] = {
      version: 8,
      sprite: orig.sprite,
      glyphs: orig.glyphs,
      sources: orig.sources,
      layers,
    };
  }
  return result;
}

export async function buildOriginalStyle() {
  const styles = {};
  for (const [name, url] of Object.entries(ORIGINAL_SERVICE_URLS)) {
    const style = await fetchJson(withFormat(url));
    absolutize(style, url);
    styles[name] = style;
  }
  return mergeStyles(styles, { glyphsFrom: "LiteLabels" });
}

export async function buildThemeStyle(themeManifest) {
  const styles = {};
  for (const [name, relPath] of Object.entries(themeManifest.styles)) {
    const styleUrl = new URL(relPath, document.baseURI).href;
    const style = await fetchJson(relPath);
    resolveThemeStyle(style, styleUrl);
    styles[name] = style;
  }
  return mergeStyles(styles, { glyphsFrom: "LiteLabels" });
}

/** Every option a picker can offer: "original" (UGRC's live basemap) plus one entry per theme
 * from docs/themes.json - built once at load so left/right pickers, defaults, and the actual
 * style builders all agree on the same list. Each option's `description` is rendered directly
 * in the Dropdown's menu - a bit of free, unobtrusive context on what each theme actually is,
 * straight from the same text the README and build already carry. */
export async function loadOptions() {
  const themes = await fetchJson("themes.json");
  const options = {
    [ORIGINAL_KEY]: {
      label: "Lite",
      description: "UGRC's original Lite basemap, fetched live and unmodified from their ArcGIS services.",
    },
  };
  for (const [name, manifest] of Object.entries(themes)) {
    options[name] = { label: manifest.label, description: manifest.description, manifest };
  }
  return options;
}
