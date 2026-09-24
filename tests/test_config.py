import json

from ugrc_styles.config import discover_themes, load_config, load_theme


def test_load_config_preserves_services_json_order(tmp_path, monkeypatch):
    # config/services.json's key order is the bottom-to-top render order the demo page merges
    # services in (see docs/index.html's mergeStyles) - load_config must not alphabetize it away.
    import ugrc_styles.config as config_mod

    monkeypatch.setattr(config_mod, "build_palette", lambda source, extra_path: {})

    config_dir = tmp_path / "config"
    (config_dir / "themes" / "t" / "services").mkdir(parents=True)
    (config_dir / "services.json").write_text(
        json.dumps({"Zeta": "https://example.com/zeta", "Alpha": "https://example.com/alpha"}),
        encoding="utf-8",
    )
    (config_dir / "themes" / "t" / "theme.json").write_text(
        json.dumps({"label": "T", "palette_source": {"type": "protomaps", "flavor": "dark", "version": "1"}}),
        encoding="utf-8",
    )
    (config_dir / "themes" / "t" / "fallback.json").write_text("{}", encoding="utf-8")
    (config_dir / "themes" / "t" / "palette_extra.json").write_text("{}", encoding="utf-8")
    for name in ("Zeta", "Alpha"):
        (config_dir / "themes" / "t" / "services" / f"{name}.json").write_text(
            json.dumps({"background": None, "rules": []}), encoding="utf-8"
        )

    cfg = load_config("t", config_dir)
    assert list(cfg.services.keys()) == ["Zeta", "Alpha"]


def test_discover_themes_finds_shadow_and_sol():
    themes = discover_themes()
    assert "shadow" in themes
    assert "sol" in themes
    assert themes == sorted(themes)


def test_load_theme_shadow_manifest():
    theme = load_theme("shadow")
    assert theme.name == "shadow"
    assert theme.sprite_transform == "invert"
    assert theme.palette_source["type"] == "protomaps"
    assert "LiteBase" in theme.sprites


def test_load_theme_sol_manifest():
    theme = load_theme("sol")
    assert theme.name == "sol"
    assert theme.sprite_transform == "none"
    assert theme.palette_source["type"] == "carto"
