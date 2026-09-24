"""Loads the config/ tree (shared service endpoints + a theme's own rules/palette extras)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ugrc_styles.palette import build_palette

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


@dataclass
class Theme:
    name: str
    label: str
    description: str
    palette_source: dict
    sprite_transform: str = "invert"
    sprites: dict = field(default_factory=dict)  # service name -> {"recolor": {icon: palette_key}}


@dataclass
class Config:
    theme: Theme
    palette: dict[str, str]
    fallback: dict
    services: dict[str, dict]  # service name -> {style_url, output, background, rules}


def discover_themes(config_dir: Path = CONFIG_DIR) -> list[str]:
    """Theme names with a config/themes/<name>/theme.json manifest, alphabetical."""
    themes_dir = config_dir / "themes"
    return sorted(p.name for p in themes_dir.iterdir() if p.is_dir() and (p / "theme.json").exists())


def load_theme(name: str, config_dir: Path = CONFIG_DIR) -> Theme:
    manifest = json.loads((config_dir / "themes" / name / "theme.json").read_text(encoding="utf-8"))
    sprites = dict(manifest.get("sprites", {}))
    sprites.pop("_about", None)
    return Theme(
        name=name,
        label=manifest["label"],
        description=manifest.get("description", ""),
        palette_source=manifest["palette_source"],
        sprite_transform=manifest.get("sprite_transform", "invert"),
        sprites=sprites,
    )


def load_config(theme_name: str, config_dir: Path = CONFIG_DIR) -> Config:
    endpoints = json.loads((config_dir / "services.json").read_text(encoding="utf-8"))
    endpoints.pop("_about", None)

    theme = load_theme(theme_name, config_dir)
    theme_dir = config_dir / "themes" / theme_name

    palette = build_palette(theme.palette_source, theme_dir / "palette_extra.json")

    fallback = json.loads((theme_dir / "fallback.json").read_text(encoding="utf-8"))
    fallback.pop("_about", None)

    # Iterated in config/services.json's own order, not alphabetically: that order is bottom ->
    # top render order once the demo page merges all 3 into one map (see docs/index.html's
    # mergeStyles) - VectorHillshade has to sit under LiteBase's fills/lines, which sit under
    # LiteLabels' text, or the wrong layer ends up covering the other two.
    services = {}
    for name in endpoints:
        svc = json.loads((theme_dir / "services" / f"{name}.json").read_text(encoding="utf-8"))
        svc["style_url"] = endpoints[name]
        svc["output"] = f"UGRC_{name}_{theme_name}.json"
        services[name] = svc

    return Config(theme=theme, palette=palette, fallback=fallback, services=services)
