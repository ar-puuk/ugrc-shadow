import json

import pytest

from ugrc_styles.palette import _carto_layer_color, build_palette


def test_carto_layer_color_plain_string():
    style = {"layers": [{"id": "water", "paint": {"fill-color": "#b0d0d6"}}]}
    assert _carto_layer_color(style, "water", "fill-color") == "#b0d0d6"


def test_carto_layer_color_takes_last_stop():
    style = {
        "layers": [
            {"id": "park", "paint": {"fill-color": {"stops": [[8, "rgba(0,0,0,0.2)"], [15, "#e0ecd3"]]}}}
        ]
    }
    assert _carto_layer_color(style, "park", "fill-color") == "#e0ecd3"


def test_carto_layer_color_missing_layer_raises():
    with pytest.raises(KeyError):
        _carto_layer_color({"layers": []}, "nope", "fill-color")


def test_build_palette_rejects_unknown_source_type(tmp_path):
    extra_path = tmp_path / "palette_extra.json"
    extra_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        build_palette({"type": "not-a-real-source"}, extra_path)


def test_build_palette_rejects_extra_overlapping_live_keys(tmp_path, monkeypatch):
    import ugrc_styles.palette as palette_mod

    monkeypatch.setitem(palette_mod._SOURCES, "fake", lambda src: {"background": "#000000"})
    extra_path = tmp_path / "palette_extra.json"
    extra_path.write_text(json.dumps({"background": "#111111"}), encoding="utf-8")
    with pytest.raises(ValueError):
        build_palette({"type": "fake"}, extra_path)
