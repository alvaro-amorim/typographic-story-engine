from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EasingName = Literal["linear", "ease_in", "ease_out", "ease_in_out"]


class SceneAnimationSpec(BaseModel):
    """Transition between two scene graphs that share persistent object IDs."""

    id: str = Field(min_length=1)
    from_scene: Path
    to_scene: Path
    duration_seconds: float = Field(default=2.0, gt=0.0, le=60.0)
    fps: int = Field(default=12, ge=1, le=60)
    easing: EasingName = "ease_in_out"

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("animation id cannot be blank")
        if any(character.isspace() for character in normalized):
            raise ValueError("animation id cannot contain whitespace")
        return normalized


class AnimationFrameState(BaseModel):
    index: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0.0)
    progress: float = Field(ge=0.0, le=1.0)
    eased_progress: float = Field(ge=0.0, le=1.0)
    object_transforms: dict[str, dict[str, float | bool]]


class AnimationManifest(BaseModel):
    id: str
    duration_seconds: float
    fps: int
    easing: EasingName
    frame_count: int
    from_scene: str
    to_scene: str
    object_ids: list[str]
    frames: list[AnimationFrameState]
