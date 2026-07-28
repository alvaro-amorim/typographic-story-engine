import random
from typing import List, Set, Tuple
from engine.models import Glyph

def distribute_glyphs(
    object_id: str,
    valid_coords: List[Tuple[int, int, float]],
    allowed_chars: Set[str],
    glyph_count: int,
    font_size_range: Tuple[int, int],
    palette: List[str], # Agora recebemos a paleta como argumento
    seed: int = 42
) -> List[Glyph]:
    
    random.seed(seed)
    glyphs = []
    chars_list = list(allowed_chars)
    
    min_size, max_size = font_size_range
    
    for i in range(glyph_count):
        x, y, dist = random.choice(valid_coords)
        char = random.choice(chars_list)
        
        base_size = min_size + (max_size - min_size) * dist
        variance = base_size * 0.20
        final_size = random.uniform(base_size - variance, base_size + variance)
        final_size = max(min_size, min(max_size, final_size)) 
        
        opacity = 1.0 - (0.40 * dist)
        
        # A MÁGICA DA COR: Escolhe aleatoriamente uma cor da paleta
        color = random.choice(palette)
        
        glyph = Glyph(
            id=f"{object_id}_glyph_{i}",
            object_id=object_id,
            character=char,
            x=float(x),
            y=float(y),
            font_size=float(final_size),
            opacity=float(opacity),
            color=color # Injetamos a cor aqui
        )
        glyphs.append(glyph)
        
    glyphs.sort(key=lambda g: g.font_size, reverse=True)
        
    return glyphs