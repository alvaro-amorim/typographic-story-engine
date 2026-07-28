from typing import List, Set, Dict, Any
from engine.models import Glyph

# Tags proibidas pelo documento de arquitetura
FORBIDDEN_TAGS = ["<path", "<rect", "<circle", "<ellipse", "<polygon", "<polyline", "<line", "<image"]

def validate_scene(glyphs: List[Glyph], allowed_chars: Set[str], svg_content: str) -> Dict[str, Any]:
    """
    Garante que não existam letras intrusas e que a geometria seja estritamente textual.
    """
    # 1. Verifica se alguma letra gerada não pertence à palavra original
    invalid_glyphs = [g.character for g in glyphs if g.character not in allowed_chars]
    
    # 2. Verifica se o renderizador usou alguma tag proibida
    found_forbidden_tags = [tag for tag in FORBIDDEN_TAGS if tag in svg_content]
    
    is_valid = len(invalid_glyphs) == 0 and len(found_forbidden_tags) == 0
    
    return {
        "is_valid": is_valid,
        "strict_mode_respected": len(found_forbidden_tags) == 0,
        "semantic_characters_respected": len(invalid_glyphs) == 0,
        "invalid_glyphs_found": invalid_glyphs,
        "forbidden_tags_found": found_forbidden_tags,
        "total_glyphs_rendered": len(glyphs)
    }