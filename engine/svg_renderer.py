from __future__ import annotations

from html import escape
from typing import Sequence

from engine.models import Glyph

LAYER_RENDER_ORDER = ("texture", "fill", "outline")


def _render_glyph(glyph: Glyph) -> str:
    transform = f"translate({glyph.x:.3f}, {glyph.y:.3f})"
    if glyph.rotation != 0:
        transform += f" rotate({glyph.rotation:.3f})"

    return (
        f'    <text x="0" y="0" font-size="{glyph.font_size:.3f}" '
        f'opacity="{glyph.opacity:.3f}" transform="{transform}" '
        f'font-family="monospace" text-anchor="middle" dominant-baseline="central" '
        f'fill="{glyph.color}" data-glyph-id="{escape(glyph.id, quote=True)}" '
        f'data-object-id="{escape(glyph.object_id, quote=True)}" '
        f'data-layer="{glyph.layer}" data-zone="{glyph.zone}">'
        f'{escape(glyph.character)}</text>'
    )


def render_to_svg(glyphs: Sequence[Glyph], width: int, height: int) -> str:
    """Render strict text-only SVG grouped into animation-ready layers."""
    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '  <g id="scene_objects">',
    ]

    known_layers = set(LAYER_RENDER_ORDER)
    for layer in LAYER_RENDER_ORDER:
        layer_glyphs = [glyph for glyph in glyphs if glyph.layer == layer]
        if not layer_glyphs:
            continue
        svg_content.append(f'  <g id="layer_{layer}" data-layer="{layer}">')
        svg_content.extend(_render_glyph(glyph) for glyph in layer_glyphs)
        svg_content.append("  </g>")

    fallback = [glyph for glyph in glyphs if glyph.layer not in known_layers]
    if fallback:
        svg_content.append('  <g id="layer_other" data-layer="other">')
        svg_content.extend(_render_glyph(glyph) for glyph in fallback)
        svg_content.append("  </g>")

    svg_content.append("  </g>")
    svg_content.append("</svg>")
    return "\n".join(svg_content)
