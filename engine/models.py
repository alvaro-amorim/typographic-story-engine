from pydantic import BaseModel
from typing import Set, Tuple, List

class SemanticObject(BaseModel):
    id: str
    word: str
    mask_path: str
    glyph_count: int = 5000
    font_size_range: Tuple[int, int] = (6, 18)
    overlap: float = 0.72
    # NOVA PROPRIEDADE: A paleta de cores do objeto
    palette: List[str] = ["#000000"] 
    
    @property
    def allowed_characters(self) -> Set[str]:
        return set(self.word.upper().replace(" ", ""))

class Glyph(BaseModel):
    id: str
    object_id: str
    character: str
    x: float
    y: float
    rotation: float = 0.0
    font_size: float
    opacity: float = 1.0
    # NOVA PROPRIEDADE: A cor individual desta letra
    color: str = "#000000"