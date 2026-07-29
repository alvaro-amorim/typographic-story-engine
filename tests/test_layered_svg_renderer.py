from engine.models import Glyph
from engine.svg_renderer import render_to_svg


def _glyph(identifier: str, layer: str) -> Glyph:
    return Glyph(
        id=identifier,
        object_id="moon",
        character="O",
        x=10,
        y=20,
        font_size=12,
        color="#172033",
        layer=layer,
    )


def test_svg_groups_layers_in_paint_order() -> None:
    svg = render_to_svg(
        [
            _glyph("outline_glyph", "outline"),
            _glyph("texture_glyph", "texture"),
            _glyph("fill_glyph", "fill"),
        ],
        width=100,
        height=80,
    )

    assert svg.index('id="layer_texture"') < svg.index('id="layer_fill"')
    assert svg.index('id="layer_fill"') < svg.index('id="layer_outline"')
    assert 'data-glyph-id="outline_glyph"' in svg
    assert 'data-layer="texture"' in svg


def test_svg_remains_strictly_typographic() -> None:
    svg = render_to_svg([_glyph("g1", "fill")], width=100, height=80)

    for forbidden in (
        "<path",
        "<rect",
        "<circle",
        "<ellipse",
        "<polygon",
        "<polyline",
        "<line",
        "<image",
    ):
        assert forbidden not in svg
    assert svg.count("<text") == 1
