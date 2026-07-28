from engine.models import Glyph
from engine.svg_renderer import render_to_svg


def _glyph(identifier: str, layer: str, role: str) -> Glyph:
    return Glyph(
        id=identifier,
        object_id="moon",
        character="O",
        x=10,
        y=20,
        font_size=12,
        color="#172033",
        layer=layer,
        style_role=role,
    )


def test_svg_groups_organic_roles_in_paint_order() -> None:
    svg = render_to_svg(
        [
            _glyph("detail", "outline", "outline_detail"),
            _glyph("shadow", "outline", "outline_shadow"),
            _glyph("texture", "texture", "texture_accent"),
            _glyph("fill", "fill", "fill_mass"),
        ],
        width=100,
        height=80,
    )

    assert svg.index('id="layer_texture"') < svg.index('id="layer_fill"')
    assert svg.index('id="layer_fill"') < svg.index('id="layer_outline"')
    assert svg.index('id="role_outline_shadow"') < svg.index(
        'id="role_outline_detail"'
    )
    assert 'data-style-role="texture_accent"' in svg
    assert 'data-style-role="outline_detail"' in svg
    assert svg.count("<text") == 4


def test_default_role_remains_backward_compatible() -> None:
    glyph = Glyph(
        id="legacy",
        object_id="moon",
        character="M",
        x=5,
        y=6,
        font_size=10,
        color="#172033",
        layer="fill",
    )

    svg = render_to_svg([glyph], width=20, height=20)

    assert 'id="role_default"' in svg
    assert 'data-style-role="default"' in svg
    assert svg.count("<text") == 1
