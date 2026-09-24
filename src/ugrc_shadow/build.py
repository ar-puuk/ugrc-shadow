"""The build pipeline, run as `uv run ugrc-shadow`.

A plain sequential script: for each of UGRC's 3 services, fetch live -> shadow -> write; then
shadow each service's own icon sprite (every icon in both LiteBase's and LiteLabels' sprites is
a non-SDF raster baked at its original light color, so our paint-level `icon-color` rules are
silently ignored - the pixels themselves have to be rewritten, same as the highway shields).
No merge step - UGRC hosts the three layers separately, so the three shadowed style JSONs stay
separate artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ugrc_shadow.config import load_config
from ugrc_shadow.engine import Shadower
from ugrc_shadow.fetch import fetch_json
from ugrc_shadow.sprites import shadow_sprite

# services whose sprite actually has icons worth shadowing (VectorHillshade declares a sprite
# field but has zero icon layers - nothing to fix there) -> the name its shadowed sprite is
# written under in docs/sprites/
SPRITES_TO_SHADOW = {
    "LiteBase": "base-icons-shadow",
    "LiteLabels": "shields-shadow",
}

# icons that must match a specific palette color exactly rather than being generically inverted:
# UGRC bakes the "Base/Railroads/0" tie-mark icon and the "Railroads" line layer beside it as the
# identical gray, and the line reaches @rail through the normal rule engine - the icon needs to
# land on that same value too, or the two visibly mismatch (icon-color is a no-op on a non-SDF
# icon, so it can't just be told "@rail" the way the line is).
SPRITE_RECOLOR = {
    "LiteBase": {"Base/Railroads/0": "rail"},  # icon name -> palette key
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def shadow_and_write_sprite(
    style: dict, sprite_name: str, sprites_dir: Path, base_url: str | None, recolor: dict[str, str] | None = None
) -> None:
    """Shadow `style`'s own sprite and repoint `style["sprite"]` at the local shadowed copy."""
    esri_sprite_base = style["sprite"]  # already absolutized to Esri's sprite URL
    sprite = shadow_sprite(esri_sprite_base, recolor)

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

    print("loading rules + live Protomaps palette ...")
    cfg = load_config()
    shadower = Shadower(cfg.palette, cfg.fallback)

    shadow_styles: dict[str, dict] = {}
    for name, svc in cfg.services.items():
        print(f"fetching {name} live from UGRC ...")
        style = fetch_json(svc["style_url"])
        shadowed, report = shadower.shadow(style, svc, svc["style_url"], source_mode="url")
        shadow_styles[name] = shadowed
        n_rule = sum(1 for r in report if r[3])
        print(f"  {name}: {len(report)} layers, {n_rule} matched a rule")

    for name, sprite_name in SPRITES_TO_SHADOW.items():
        print(f"shadowing {name}'s icon sprite ...")
        recolor = {icon: cfg.palette[key] for icon, key in SPRITE_RECOLOR.get(name, {}).items()}
        shadow_and_write_sprite(shadow_styles[name], sprite_name, sprites_dir, base_url, recolor)

    for name, svc in cfg.services.items():
        out_path = styles_dir / svc["output"]
        write_json(out_path, shadow_styles[name])
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
            "used to point each shadowed style's sprite at an absolute, standalone-usable URL. "
            "Defaults to a relative path, which is fine for the docs/ demo but not for someone taking "
            "a style JSON elsewhere on its own."
        ),
    )
    args = ap.parse_args(argv)
    build(Path(args.out_dir), args.base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
