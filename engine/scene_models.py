from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SceneTransform(BaseModel):
    """Places a local mask-centered object inside the scene canvas."""

    x: float
    y: float
    scale: float = Field(default=1.0, gt=0.0)
    rotation: float = 0.0


class SceneObject(BaseModel):
    """A semantic object rendered independently before scene composition."""

    id: str = Field(min_length=1)
    word: str = Field(min_length=1)
    mask_path: str = Field(min_length=1)
    transform: SceneTransform
    z_index: int = 0
    glyph_count: int = Field(default=5000, gt=0)
    font_size_range: tuple[float, float] = (8.0, 28.0)
    palette: list[str] = Field(default_factory=lambda: ["#2C303A"], min_length=1)
    seed: int = 817392
    enabled: bool = True
    renderer: Literal["balanced"] = "balanced"

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("object id cannot be blank")
        if any(character.isspace() for character in normalized):
            raise ValueError("object id cannot contain whitespace")
        return normalized

    @field_validator("word")
    @classmethod
    def normalize_word(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not any(character.isalpha() for character in normalized):
            raise ValueError("word must contain at least one alphabetic character")
        return normalized

    @field_validator("font_size_range")
    @classmethod
    def validate_font_size_range(
        cls, value: tuple[float, float]
    ) -> tuple[float, float]:
        minimum, maximum = value
        if minimum <= 0 or maximum <= 0 or minimum > maximum:
            raise ValueError("font_size_range must contain positive ascending values")
        return float(minimum), float(maximum)

    def resolve_mask_path(self, base_dir: Path) -> Path:
        candidate = Path(self.mask_path)
        return candidate if candidate.is_absolute() else base_dir / candidate


class SceneDefinition(BaseModel):
    """Serializable scene graph consumed by the multi-object compositor."""

    id: str = Field(min_length=1)
    width: int = Field(default=1600, gt=0)
    height: int = Field(default=900, gt=0)
    background: Literal["transparent"] = "transparent"
    objects: list[SceneObject] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scene id cannot be blank")
        if any(character.isspace() for character in normalized):
            raise ValueError("scene id cannot contain whitespace")
        return normalized

    @model_validator(mode="after")
    def validate_unique_object_ids(self) -> "SceneDefinition":
        identifiers = [item.id for item in self.objects]
        duplicates = sorted(
            identifier
            for identifier in set(identifiers)
            if identifiers.count(identifier) > 1
        )
        if duplicates:
            raise ValueError(
                "scene object ids must be unique: " + ", ".join(duplicates)
            )
        return self
