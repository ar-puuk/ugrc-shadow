"""The build pipeline, run as `uv run ugrc-shadow`.

A plain sequential script: for each of UGRC's 3 services, fetch live -> darken -> write; then
darken each service's own icon sprite (every icon in both LiteBase's and LiteLabels' sprites is
a non-SDF raster baked at its original light color, so our paint-level `icon-color` rules are
silently ignored - the pixels themselves have to be rewritten, same as the highway shields).
No merge step - UGRC hosts the three layers separately, so the three darkened style JSONs stay
separate artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ugrc_shadow.config import load_config
from ugrc_shadow.engine import Darkener
from ugrc_shadow.fetch import fetch_json
from ugrc_shadow.sprites import darken_sprite

# services whose sprite actually has icons worth darkening (VectorHillshade declares a sprite
# field but has zero icon layers - nothing to fix there) -> the name its darkened sprite is
# written under in docs/sprites/
SPRITES_TO_DARKEN = {
    "LiteBase": "base-icons-dark",
    "LiteLabels": "shields-dark",
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def darken_and_write_sprite(style: dict, sprite_name: str, sprites_dir: Path, base_url: str | None) -> None:
    """Darken `style`'s own sprite and repoint `style["sprite"]` at the local darkened copy."""
    esri_sprite_base = style["sprite"]  # already absolutized to Esri's sprite URL
    sprite = darken_sprite(esri_sprite_base)

    write_json(sprites_dir / f"{sprite_name}.json", sprite["json"])
    (sprites_dir / f"{sprite_name}.png").write_bytes(sprite["png"])
    if sprite["json@2x"] is not None:
        write_json(sprites_dir / f"{sprite_name}@2x.json", sprite["json@2x"])
        (sprites_dir / f"{sprite_name}@2x.png").write_bytes(sprite["png@2x"])
        print(f"  wrote {sprite_name}.{{json,png}} + @2x")
    else:
        print(f"  wrote {sprite_name}.{{json,png}} (no @2x sheet published by UGRC)")

    style["sprite"] = (
        f"{base_url.rstrip('/')}/sprites/{sprite_name}" if base_url else f"../sprites/{sprite_name}"
    )


def build(out_dir: Path, base_url: str | None = None) -> None:
    styles_dir = out_dir / "styles"
    sprites_dir = out_dir / "sprites"
    styles_dir.mkdir(parents=True, exist_ok=True)
    sprites_dir.mkdir(parents=True, exist_ok=True)

    print("loading rules + live Protomaps dark palette ...")
    cfg = load_config()
    darkener = Darkener(cfg.palette, cfg.fallback)

    dark_styles: dict[str, dict] = {}
    for name, svc in cfg.services.items():
        print(f"fetching {name} live from UGRC ...")
        style = fetch_json(svc["style_url"])
        dark, report = darkener.darken(style, svc, svc["style_url"])
        dark_styles[name] = dark
        n_rule = sum(1 for r in report if r[3])
        print(f"  {name}: {len(report)} layers, {n_rule} matched a rule")

    for name, sprite_name in SPRITES_TO_DARKEN.items():
        print(f"darkening {name}'s icon sprite ...")
        darken_and_write_sprite(dark_styles[name], sprite_name, sprites_dir, base_url)

    for name, svc in cfg.services.items():
        out_path = styles_dir / svc["output"]
        write_json(out_path, dark_styles[name])
        print(f"wrote {out_path}")

    print("done.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default="docs", help="where to write styles/ and sprites/ (default: docs)")
    ap.add_argument(
        "--base-url",
        default=None,
        help=(
            "absolute base URL the site is published at (e.g. https://<user>.github.io/ugrc-shadow), "
            "used to point each darkened style's sprite at an absolute, standalone-usable URL. "
            "Defaults to a relative path, which is fine for the docs/ demo but not for someone taking "
            "a style JSON elsewhere on its own."
        ),
    )
    args = ap.parse_args(argv)
    build(Path(args.out_dir), args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
