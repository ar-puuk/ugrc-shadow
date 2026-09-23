"""Loads the config/ tree (our own rules + palette extras) and resolves the live palette."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ugrc_shadow.palette import build_palette

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


@dataclass
class Config:
    palette: dict[str, str]
    fallback: dict
    services: dict[str, dict]  # service name -> {style_url, output, background, rules}


def load_config(config_dir: Path = CONFIG_DIR) -> Config:
    palette = build_palette(config_dir / "palette_extra.json")
    fallback = json.loads((config_dir / "fallback.json").read_text(encoding="utf-8"))
    fallback.pop("_about", None)

    services = {}
    for path in sorted((config_dir / "services").glob("*.json")):
        services[path.stem] = json.loads(path.read_text(encoding="utf-8"))

    return Config(palette=palette, fallback=fallback, services=services)
