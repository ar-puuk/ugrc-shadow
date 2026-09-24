from ugrc_styles.engine import Shadower


def test_rule_matches_source_layer_and_type():
    rule = {"match": {"source_layer": "^Roads$", "type": "line"}}
    assert Shadower.rule_matches(rule, {"type": "line", "source-layer": "Roads"})
    assert not Shadower.rule_matches(rule, {"type": "fill", "source-layer": "Roads"})
    assert not Shadower.rule_matches(rule, {"type": "line", "source-layer": "RoadsAlt"})


def test_rule_matches_paint_regex():
    rule = {"match": {"paint": {"line-color": "^#F"}}}
    assert Shadower.rule_matches(rule, {"paint": {"line-color": "#ffffff"}})
    assert not Shadower.rule_matches(rule, {"paint": {"line-color": "#000000"}})


def _service():
    return {
        "rules": [
            {
                "note": "roads",
                "match": {"source_layer": "^Roads$", "type": "line"},
                "paint": {"line-color": "@road"},
            }
        ],
        "background": None,
    }


def _style():
    return {
        "sources": {},
        "sprite": "rel/sprite",
        "glyphs": "rel/{fontstack}/{range}.pbf",
        "layers": [
            {"id": "roads", "type": "line", "source-layer": "Roads", "paint": {"line-color": "#ffffff"}},
            {"id": "other", "type": "fill", "source-layer": "Other", "paint": {"fill-color": "#eeeeee"}},
        ],
    }


def _shadower():
    palette = {"road": "#ff0000", "halo": "#000000"}
    fallback = {"fill": {"l_min": 0.10, "l_max": 0.20, "s_mult": 0.5}, "skip_props": []}
    return Shadower(palette, fallback)


def test_shadow_applies_matched_rule():
    shadowed, _report = _shadower().shadow(_style(), _service(), "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert roads["paint"]["line-color"] == "#ff0000"


def test_shadow_falls_back_unmatched_color_into_shadow_band():
    shadowed, _ = _shadower().shadow(_style(), _service(), "https://example.com/services/Foo/resources/styles/root.json")
    other = next(ly for ly in shadowed["layers"] if ly["id"] == "other")
    # #eeeeee (lightness ~0.93) must compress into the [0.10, 0.20] fallback band, i.e. get much darker
    assert other["paint"]["fill-color"] != "#eeeeee"
    assert other["paint"]["fill-color"].lstrip("#")[:2] < "40"


def test_shadow_absolutizes_sprite_and_glyphs():
    shadowed, _ = _shadower().shadow(_style(), _service(), "https://example.com/services/Foo/resources/styles/root.json")
    assert shadowed["sprite"].startswith("https://example.com/")
    assert shadowed["glyphs"].startswith("https://example.com/")


def test_shadow_source_mode_url_keeps_esri_service_reference():
    # UGRC's own root.json points sources at itself via a relative "url", not a tiles template -
    # source_mode="url" must preserve that shape (just absolutized) so the output stays a
    # structural match for Esri's style, since it's headed for ArcGIS Online, not just MapLibre.
    style = _style()
    style["sources"] = {"esri": {"type": "vector", "url": "../../"}}
    shadowed, _ = _shadower().shadow(
        style,
        _service(),
        "https://example.com/services/Foo/resources/styles/root.json",
        source_mode="url",
    )
    src = shadowed["sources"]["esri"]
    assert src["url"] == "https://example.com/services/Foo/"
    assert "tiles" not in src


def test_shadow_skip_rule_leaves_layer_untouched():
    service = {
        "rules": [{"note": "skip it", "match": {"id": "^roads$"}, "skip": True}],
        "background": None,
    }
    shadowed, _report = _shadower().shadow(_style(), service, "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert roads["paint"]["line-color"] == "#ffffff"
