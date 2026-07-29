from __future__ import annotations

from html import escape
from typing import Sequence

from engine.models import Glyph

LAYER_RENDER_ORDER = ("texture", "fill", "outline")
ROLE_RENDER_ORDER = {
    "texture": ("texture_accent", "default"),
    "fill": ("fill_mass", "default"),
    "outline": ("outline_shadow", "outline_detail", "default"),
}


def _group_id(prefix: str, name: str) -> str:
    return f"{prefix}_{name}" if prefix else name


def render_glyph_element(glyph: Glyph, indent: str = "      ") -> str:
    """Render one visible glyph. All visible scene geometry remains text-only."""
    transform = f"translate({glyph.x:.3f}, {glyph.y:.3f})"
    if glyph.rotation != 0:
        transform += f" rotate({glyph.rotation:.3f})"

    return (
        f'{indent}<text x="0" y="0" font-size="{glyph.font_size:.3f}" '
        f'opacity="{glyph.opacity:.3f}" transform="{transform}" '
        f'font-family="monospace" text-anchor="middle" dominant-baseline="central" '
        f'fill="{glyph.color}" data-glyph-id="{escape(glyph.id, quote=True)}" '
        f'data-object-id="{escape(glyph.object_id, quote=True)}" '
        f'data-layer="{glyph.layer}" data-zone="{glyph.zone}" '
        f'data-style-role="{glyph.style_role}">'
        f'{escape(glyph.character)}</text>'
    )


def render_glyph_groups(
    glyphs: Sequence[Glyph],
    *,
    id_prefix: str = "",
    indent: str = "  ",
) -> list[str]:
    """Render reusable layer/role groups for a single semantic object."""
    content: list[str] = []
    known_layers = set(LAYER_RENDER_ORDER)

    for layer in LAYER_RENDER_ORDER:
        layer_glyphs = [glyph for glyph in glyphs if glyph.layer == layer]
        if not layer_glyphs:
            continue
        layer_id = _group_id(id_prefix, f"layer_{layer}")
        content.append(
            f'{indent}<g id="{escape(layer_id, quote=True)}" data-layer="{layer}">'
        )
        role_indent = indent + "  "
        glyph_indent = role_indent + "  "
        known_roles = set(ROLE_RENDER_ORDER[layer])
        for role in ROLE_RENDER_ORDER[layer]:
            role_glyphs = [
                glyph for glyph in layer_glyphs if glyph.style_role == role
            ]
            if not role_glyphs:
                continue
            role_id = _group_id(id_prefix, f"role_{role}")
            content.append(
                f'{role_indent}<g id="{escape(role_id, quote=True)}" '
                f'data-style-role="{role}">'
            )
            content.extend(
                render_glyph_element(glyph, indent=glyph_indent)
                for glyph in role_glyphs
            )
            content.append(f"{role_indent}</g>")

        fallback = [
            glyph for glyph in layer_glyphs if glyph.style_role not in known_roles
        ]
        if fallback:
            role_id = _group_id(id_prefix, "role_other")
            content.append(
                f'{role_indent}<g id="{escape(role_id, quote=True)}" '
                'data-style-role="other">'
            )
            content.extend(
                render_glyph_element(glyph, indent=glyph_indent) for glyph in fallback
            )
            content.append(f"{role_indent}</g>")
        content.append(f"{indent}</g>")

    fallback_layers = [glyph for glyph in glyphs if glyph.layer not in known_layers]
    if fallback_layers:
        layer_id = _group_id(id_prefix, "layer_other")
        content.append(
            f'{indent}<g id="{escape(layer_id, quote=True)}" data-layer="other">'
        )
        content.extend(
            render_glyph_element(glyph, indent=indent + "  ")
            for glyph in fallback_layers
        )
        content.append(f"{indent}</g>")

    return content


def render_to_svg(glyphs: Sequence[Glyph], width: int, height: int) -> str:
    """Render one object in strict text-only SVG."""
    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '  <g id="scene_objects">',
    ]
    svg_content.extend(render_glyph_groups(glyphs, indent="    "))
    svg_content.append("  </g>")
    svg_content.append("</svg>")
    return "\n".join(svg_content)
