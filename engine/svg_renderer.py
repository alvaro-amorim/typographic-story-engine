from typing import List
from engine.models import Glyph

def render_to_svg(glyphs: List[Glyph], width: int, height: int) -> str:
    svg_content = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
    ]
    
    svg_content.append('  <g id="scene_objects">')
    
    for glyph in glyphs:
        transform = f'translate({glyph.x}, {glyph.y})'
        if glyph.rotation != 0:
            transform += f' rotate({glyph.rotation})'
            
        svg_content.append(
            f'    <text x="0" y="0" font-size="{glyph.font_size:.1f}" '
            f'opacity="{glyph.opacity:.2f}" transform="{transform}" '
            f'font-family="monospace" text-anchor="middle" dominant-baseline="central" '
            f'fill="{glyph.color}">{glyph.character}</text>' # AGORA USA A COR DO GLYPH
        )
        
    svg_content.append('  </g>')
    svg_content.append('</svg>')
    
    return "\n".join(svg_content)