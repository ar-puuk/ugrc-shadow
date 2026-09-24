import pytest

from ugrc_styles.engine import Shadower, remap_icon_images


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


def test_remap_icon_images_renames_matching_only():
    style = {
        "layers": [
            {"id": "a", "layout": {"icon-image": "Base/Foo"}},
            {"id": "b", "layout": {"icon-image": "Base/Bar"}},
            {"id": "c", "layout": {"text-field": "x"}},  # no icon-image at all
            {"id": "d"},  # no layout at all
        ]
    }
    remap_icon_images(style, {"Base/Foo": "Overlay/Foo"})
    by_id = {ly["id"]: ly for ly in style["layers"]}
    assert by_id["a"]["layout"]["icon-image"] == "Overlay/Foo"
    assert by_id["b"]["layout"]["icon-image"] == "Base/Bar"  # unmapped name left as-is


def test_shadow_scale_multiplies_existing_numeric_value():
    style = _style()
    next(ly for ly in style["layers"] if ly["id"] == "roads")["paint"]["line-width"] = 2.0
    service = {
        "rules": [{"note": "narrower", "match": {"id": "^roads$"}, "paint": {"line-width": {"scale": 0.85}}}],
        "background": None,
    }
    shadowed, _ = _shadower().shadow(style, service, "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert roads["paint"]["line-width"] == pytest.approx(1.7)


def test_shadow_scale_multiplies_each_element_of_a_list_value():
    # e.g. line-dasharray: scaling every element by the same factor preserves whatever ratio
    # Esri already tuned between dash/gap (and, across differently-sized sibling layers that
    # share this rule, whatever cross-layer pixel-length consistency Esri already baked in).
    style = _style()
    next(ly for ly in style["layers"] if ly["id"] == "roads")["paint"]["line-dasharray"] = [0.8, 1.6]
    service = {
        "rules": [{"note": "wider dashes", "match": {"id": "^roads$"}, "paint": {"line-dasharray": {"scale": 3}}}],
        "background": None,
    }
    shadowed, _ = _shadower().shadow(style, service, "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert roads["paint"]["line-dasharray"] == pytest.approx([2.4, 4.8])


def test_shadow_scale_skips_layer_missing_the_property():
    # "roads" (type line) has no line-width preset in the fixture - scale must leave it absent
    # rather than raising or inventing a value.
    service = {
        "rules": [{"note": "narrower", "match": {"id": "^roads$"}, "paint": {"line-width": {"scale": 0.85}}}],
        "background": None,
    }
    shadowed, _ = _shadower().shadow(_style(), service, "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert "line-width" not in roads["paint"]


def test_shadow_skip_rule_leaves_layer_untouched():
    service = {
        "rules": [{"note": "skip it", "match": {"id": "^roads$"}, "skip": True}],
        "background": None,
    }
    shadowed, _report = _shadower().shadow(_style(), service, "https://example.com/services/Foo/resources/styles/root.json")
    roads = next(ly for ly in shadowed["layers"] if ly["id"] == "roads")
    assert roads["paint"]["line-color"] == "#ffffff"
