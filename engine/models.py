from __future__ import annotations

import re
from typing import List, Literal, Set, Tuple

from pydantic import BaseModel, Field, field_validator

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _normalized_characters(word: str) -> Tuple[str, ...]:
    """Return uppercase semantic characters while preserving order and repeats."""
    return tuple(character for character in word.upper() if character.isalpha())


class SemanticObject(BaseModel):
    id: str = Field(min_length=1)
    word: str = Field(min_length=1)
    mask_path: str = Field(min_length=1)
    glyph_count: int = Field(default=5000, gt=0)
    font_size_range: Tuple[float, float] = (6.0, 18.0)
    overlap: float = Field(default=0.72, ge=0.0, le=1.0)
    palette: List[str] = Field(default_factory=lambda: ["#000000"], min_length=1)
    seed: int = 42

    @field_validator("word")
    @classmethod
    def validate_word(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not _normalized_characters(normalized):
            raise ValueError("word must contain at least one alphabetic character")
        return normalized

    @field_validator("font_size_range")
    @classmethod
    def validate_font_size_range(
        cls, value: Tuple[float, float]
    ) -> Tuple[float, float]:
        minimum, maximum = value
        if minimum <= 0 or maximum <= 0:
            raise ValueError("font sizes must be greater than zero")
        if minimum > maximum:
            raise ValueError("font_size_range minimum cannot exceed maximum")
        return float(minimum), float(maximum)

    @field_validator("palette")
    @classmethod
    def validate_palette(cls, value: List[str]) -> List[str]:
        normalized = [color.upper() for color in value]
        invalid = [color for color in normalized if not _HEX_COLOR.fullmatch(color)]
        if invalid:
            raise ValueError(
                "palette colors must use six-digit hexadecimal format: "
                + ", ".join(invalid)
            )
        return normalized

    @property
    def character_sequence(self) -> Tuple[str, ...]:
        """Characters used for sampling, preserving word order and frequency."""
        return _normalized_characters(self.word)

    @property
    def allowed_characters(self) -> Set[str]:
        """Unique characters accepted by strict semantic validation."""
        return set(self.character_sequence)


class Glyph(BaseModel):
    id: str = Field(min_length=1)
    object_id: str = Field(min_length=1)
    character: str = Field(min_length=1, max_length=1)
    x: float
    y: float
    rotation: float = 0.0
    font_size: float = Field(gt=0.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    color: str = "#000000"
    zone: Literal["edge", "mid", "core"] = "mid"
    layer: Literal["outline", "fill", "texture"] = "fill"
    depth: float = Field(default=0.0, ge=0.0, le=1.0)
    orientation_angle: float | None = None
    orientation_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    orientation_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    orientation_source: Literal["random", "tangent"] = "random"

    @field_validator("character")
    @classmethod
    def normalize_character(cls, value: str) -> str:
        return value.upper()

    @field_validator("color")
    @classmethod
    def validate_color(cls, value: str) -> str:
        normalized = value.upper()
        if not _HEX_COLOR.fullmatch(normalized):
            raise ValueError("color must use six-digit hexadecimal format")
        return normalized
