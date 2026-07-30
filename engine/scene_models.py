from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


class SceneTransform(BaseModel):
    """Transform applied to an object group without regenerating local glyphs."""

    x: float = 0.0
    y: float = 0.0
    scale_x: float = Field(default=1.0, gt=0.0)
    scale_y: float = Field(default=1.0, gt=0.0)
    rotation: float = 0.0
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class SceneObjectSpec(BaseModel):
    """A semantic object backed by a previously rendered glyph-state JSON file."""

    id: str = Field(min_length=1)
    word: str = Field(min_length=1)
    glyphs_path: Path
    transform: SceneTransform = Field(default_factory=SceneTransform)
    z_index: int = 0
    visible: bool = True

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
        normalized = "".join(character for character in value.upper() if character.isalpha())
        if not normalized:
            raise ValueError("word must contain at least one alphabetic character")
        return normalized

    @property
    def allowed_characters(self) -> set[str]:
        return set(self.word)


class SceneSpec(BaseModel):
    """Serializable scene graph for deterministic multi-object composition."""

    id: str = Field(min_length=1)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    background: str = "transparent"
    objects: list[SceneObjectSpec] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scene id cannot be blank")
        if any(character.isspace() for character in normalized):
            raise ValueError("scene id cannot contain whitespace")
        return normalized

    @field_validator("background")
    @classmethod
    def validate_background(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "transparent":
            return normalized
        if not _HEX_COLOR.fullmatch(value):
            raise ValueError(
                "background must be 'transparent' or a six-digit hexadecimal color"
            )
        return value.upper()

    @model_validator(mode="after")
    def validate_unique_object_ids(self) -> "SceneSpec":
        identifiers = [item.id for item in self.objects]
        duplicates = sorted(
            {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
        )
        if duplicates:
            raise ValueError("scene object IDs must be unique: " + ", ".join(duplicates))
        return self


class SceneObjectState(BaseModel):
    """Compact object metadata stored in the generated scene-state JSON."""

    id: str
    word: str
    source_glyphs_path: str
    source_glyph_count: int
    z_index: int
    visible: bool
    transform: SceneTransform


class SceneState(BaseModel):
    """Generated scene state; glyph coordinates remain local to each object."""

    id: str
    width: int
    height: int
    background: str
    objects: list[SceneObjectState]
