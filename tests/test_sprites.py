import io

from PIL import Image

from ugrc_styles.sprites import merge_sprites, shadow_sprite_image


def _png(pixels: list[list[tuple[int, int, int, int]]]) -> bytes:
    h, w = len(pixels), len(pixels[0])
    img = Image.new("RGBA", (w, h))
    for y, row in enumerate(pixels):
        for x, px in enumerate(row):
            img.putpixel((x, y), px)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _pixels(png_bytes: bytes) -> list[list[tuple[int, int, int, int]]]:
    img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    w, h = img.size
    return [[img.getpixel((x, y)) for x in range(w)] for y in range(h)]


def test_shadow_sprite_image_transform_none_is_identity():
    png = _png([[(10, 20, 30, 255), (0, 0, 0, 0)]])
    out = shadow_sprite_image(png, transform="none")
    assert _pixels(out) == [[(10, 20, 30, 255), (0, 0, 0, 0)]]


def test_merge_sprites_copies_semi_transparent_pixels_without_blending():
    # a semi-transparent edge pixel pasted onto a transparent canvas must come through byte-for-
    # byte, not get alpha-blended toward black (regression test for a real bug: using the source
    # image as its own paste mask lerps color+alpha against the background instead of copying).
    base_json = {}
    base_png = _png([[(0, 0, 0, 0)]])
    extra_json = {"icon": {"x": 0, "y": 0, "width": 2, "height": 1, "pixelRatio": 1, "sdf": False}}
    extra_png = _png([[(199, 194, 182, 128), (199, 194, 182, 255)]])

    merged = merge_sprites(
        {"json": base_json, "png": base_png, "json@2x": None, "png@2x": None},
        {"json": extra_json, "png": extra_png, "json@2x": None, "png@2x": None},
        ["icon"],
    )

    box = merged["json"]["icon"]
    pixels = _pixels(merged["png"])
    row = pixels[box["y"]][box["x"] : box["x"] + box["width"]]
    assert row == [(199, 194, 182, 128), (199, 194, 182, 255)]


def test_merge_sprites_packs_icons_beneath_existing_sheet():
    base_json = {"existing": {"x": 0, "y": 0, "width": 1, "height": 1, "pixelRatio": 1, "sdf": False}}
    base_png = _png([[(1, 2, 3, 255)]])
    extra_json = {"icon": {"x": 5, "y": 5, "width": 1, "height": 1, "pixelRatio": 1, "sdf": False}}
    extra_png = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    extra_png.putpixel((5, 5), (9, 9, 9, 255))
    buf = io.BytesIO()
    extra_png.save(buf, format="PNG")

    merged = merge_sprites(
        {"json": base_json, "png": base_png, "json@2x": None, "png@2x": None},
        {"json": extra_json, "png": buf.getvalue(), "json@2x": None, "png@2x": None},
        ["icon"],
    )

    assert merged["json"]["existing"] == base_json["existing"]  # untouched
    assert merged["json"]["icon"]["y"] == 1  # packed in a new row beneath the 1px-tall base sheet
    pixels = _pixels(merged["png"])
    box = merged["json"]["icon"]
    assert pixels[box["y"]][box["x"]] == (9, 9, 9, 255)
