"""The build pipeline, run as `uv run ugrc-styles`.

For each theme in config/themes/ (or just the ones named on the command line), and for each of
UGRC's 3 services: fetch live -> restyle -> write; then rework that service's own icon sprite
(every icon in both LiteBase's and LiteLabels' sprites is a non-SDF raster baked at its original
color, so our paint-level `icon-color` rules are silently ignored - the pixels themselves have to
be rewritten, same as the highway shields). No merge step - UGRC hosts the three layers
separately, so the three restyled style JSONs stay separate artifacts, once per theme.

Also writes docs/themes.json, a small manifest the demo page (docs/index.html) reads at runtime
to learn which themes exist and where their style JSONs live - so adding a new theme under
config/themes/ never requires touching the page's JS.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ugrc_styles.config import Config, discover_themes, load_config
from ugrc_styles.engine import Shadower, remap_icon_images
from ugrc_styles.fetch import fetch_json
from ugrc_styles.sprites import shadow_sprite

# UGRC service name -> the basename its theme-shadowed sprite is published under in
# docs/<theme>/sprites/ (VectorHillshade declares a sprite field but has zero icon layers -
# nothing to fix there, so it's simply absent from every theme's theme.json "sprites" section).
SPRITE_BASENAME = {
    "LiteBase": "base-icons",
    "LiteLabels": "shields",
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def shadow_and_write_sprite(
    style: dict,
    sprite_base_url: str,
    sprite_name: str,
    sprites_dir: Path,
    base_url: str | None,
    recolor: dict[str, str] | None,
    transform: str,
) -> None:
    """Rework the sprite at `sprite_base_url` per the theme's transform and repoint
    `style["sprite"]` at the local reworked copy."""
    sprite = shadow_sprite(sprite_base_url, recolor, transform)

    write_json(sprites_dir / f"{sprite_name}.json", sprite["json"])
    (sprites_dir / f"{sprite_name}.png").write_bytes(sprite["png"])
    if sprite["json@2x"] is not None:
        write_json(sprites_dir / f"{sprite_name}@2x.json", sprite["json@2x"])
        (sprites_dir / f"{sprite_name}@2x.png").write_bytes(sprite["png@2x"])
        print(f"  wrote {sprite_name}.{{json,png}} + @2x")
    else:
        print(f"  wrote {sprite_name}.{{json,png}} (no @2x sheet published by UGRC)")

    style["sprite"] = f"{base_url.rstrip('/')}/sprites/{sprite_name}" if base_url else f"../sprites/{sprite_name}"


def build_theme(cfg: Config, theme_dir: Path, base_url: str | None = None) -> dict:
    """Builds one theme into <out_dir>/<theme>/{styles,sprites}. Returns the docs/themes.json
    entry describing it."""
    styles_dir = theme_dir / "styles"
    sprites_dir = theme_dir / "sprites"
    styles_dir.mkdir(parents=True, exist_ok=True)
    sprites_dir.mkdir(parents=True, exist_ok=True)

    shadower = Shadower(cfg.palette, cfg.fallback)

    shadow_styles: dict[str, dict] = {}
    for name, svc in cfg.services.items():
        print(f"fetching {name} live from UGRC ...")
        style = fetch_json(svc["style_url"])
        shadowed, report = shadower.shadow(style, svc, svc["style_url"], source_mode="url")
        shadow_styles[name] = shadowed
        n_rule = sum(1 for r in report if r[3])
        print(f"  {name}: {len(report)} layers, {n_rule} matched a rule")

    for name, sprite_cfg in cfg.theme.sprites.items():
        if name not in shadow_styles:
            continue
        style = shadow_styles[name]
        icon_remap = sprite_cfg.get("icon_remap")
        if icon_remap:
            remap_icon_images(style, icon_remap)

        # a theme may point a service at a different sprite sheet entirely (e.g. sol borrows
        # Vector_Overlay's colorful icons instead of LiteBase/LiteLabels' own muted ones) -
        # "source" names that sheet's base URL; absent, fall back to the service's own sprite.
        sprite_base_url = sprite_cfg.get("source") or style["sprite"]  # already absolutized

        print(f"reworking {name}'s icon sprite ...")
        sprite_name = f"{SPRITE_BASENAME[name]}-{cfg.theme.name}"
        recolor = {icon: cfg.palette[key] for icon, key in sprite_cfg.get("recolor", {}).items()}
        shadow_and_write_sprite(
            style, sprite_base_url, sprite_name, sprites_dir, base_url, recolor, cfg.theme.sprite_transform
        )

    style_paths = {}
    for name, svc in cfg.services.items():
        out_path = styles_dir / svc["output"]
        write_json(out_path, shadow_styles[name])
        print(f"wrote {out_path}")
        style_paths[name] = f"{cfg.theme.name}/styles/{svc['output']}"

    return {"label": cfg.theme.label, "description": cfg.theme.description, "styles": style_paths}


def build(out_dir: Path, theme_names: list[str] | None = None, base_url: str | None = None) -> None:
    theme_names = theme_names or discover_themes()
    if not theme_names:
        raise ValueError("no themes found under config/themes/")

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for theme_name in theme_names:
        print(f"== {theme_name} ==")
        print("loading rules + live palette ...")
        cfg = load_config(theme_name)
        theme_base_url = f"{base_url.rstrip('/')}/{theme_name}" if base_url else None
        manifest[theme_name] = build_theme(cfg, out_dir / theme_name, theme_base_url)

    write_json(out_dir / "themes.json", manifest)
    print(f"wrote {out_dir / 'themes.json'}")
    print("done.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--theme",
        action="append",
        dest="themes",
        metavar="NAME",
        help="build only this theme (repeatable). Defaults to every theme under config/themes/.",
    )
    ap.add_argument("--out-dir", default="docs", help="where to write <theme>/styles + <theme>/sprites (default: docs)")
    ap.add_argument(
        "--base-url",
        default=None,
        help=(
            "absolute base URL the site is published at (e.g. https://<user>.github.io/ugrc-styles), "
            "used to point each theme's sprites at an absolute, standalone-usable URL. "
            "Defaults to a relative path, which is fine for the docs/ demo but not for someone taking "
            "a style JSON elsewhere on its own."
        ),
    )
    args = ap.parse_args(argv)
    build(Path(args.out_dir), args.themes, args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
