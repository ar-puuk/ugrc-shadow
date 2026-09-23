from ugrc_shadow.colors import fmt_color, hex_key, invert_lightness, parse_color


def test_parse_hex6():
    assert parse_color("#1f1f1f") == (31, 31, 31, 1.0)


def test_parse_hex3_expands():
    assert parse_color("#fff") == (255, 255, 255, 1.0)


def test_parse_hex8_alpha():
    r, g, b, a = parse_color("#ff000080")
    assert (r, g, b) == (255, 0, 0)
    assert abs(a - 128 / 255) < 1e-6


def test_parse_rgba():
    assert parse_color("rgba(31,31,31,0.5)") == (31.0, 31.0, 31.0, 0.5)


def test_parse_hsla_roundtrips_rgb():
    r, g, b, a = parse_color("hsla(0,0%,12%,1)")
    assert round(r) == round(g) == round(b) == round(0.12 * 255)
    assert a == 1.0


def test_parse_named_and_invalid():
    assert parse_color("transparent") == (0, 0, 0, 0.0)
    assert parse_color("not-a-color") is None
    assert parse_color(123) is None


def test_fmt_color_opaque_is_hex():
    assert fmt_color(31, 31, 31, 1.0) == "#1f1f1f"


def test_fmt_color_alpha_is_rgba():
    assert fmt_color(255, 0, 0, 0.5) == "rgba(255,0,0,0.5)"


def test_hex_key_uppercase_ignores_alpha():
    assert hex_key((31, 31, 31, 0.2)) == "#1F1F1F"


def test_invert_lightness_flips_white_to_black():
    r, g, b, a = invert_lightness((255, 255, 255, 1.0))
    assert (round(r), round(g), round(b)) == (0, 0, 0)
    assert a == 1.0


def test_invert_lightness_flips_black_to_white():
    r, g, b, _a = invert_lightness((0, 0, 0, 1.0))
    assert (round(r), round(g), round(b)) == (255, 255, 255)


def test_invert_lightness_preserves_hue_of_a_color():
    # a light, unsaturated red should darken but stay red-ish, not shift to cyan
    # like a literal channel invert (255-r, 255-g, 255-b) would.
    r, g, b, _a = invert_lightness((220, 60, 60, 1.0))
    assert r > g and r > b  # still reads as red
    assert r < 220  # but darker than the original
