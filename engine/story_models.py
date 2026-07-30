from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MovementDirection = Literal["left", "right", "pose"]


class StoryDecision(BaseModel):
    """Provider-neutral decision validated before scene generation."""

    subject_asset_id: str = Field(min_length=1)
    included_asset_ids: list[str] = Field(default_factory=list)
    movement_direction: MovementDirection = "pose"
    movement_fraction: float = Field(default=0.28, ge=0.0, le=1.0)

    @field_validator("included_asset_ids")
    @classmethod
    def unique_asset_ids(cls, values: list[str]) -> list[str]:
        unique: list[str] = []
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in unique:
                unique.append(normalized)
        return unique


class StoryPlanManifest(BaseModel):
    """Serializable explanation of how a short story became two scenes."""

    id: str
    story: str
    normalized_story: str
    template_id: str
    subject_asset_id: str
    included_asset_ids: list[str]
    movement_direction: MovementDirection
    movement_distance: float
    scene_files: list[str] = Field(min_length=2, max_length=2)
    animation_file: str
    registry_file: str
    planner_provider: str = "deterministic"
    planner_model: str | None = None
    planner_fallback_used: bool = False
    planner_error: str | None = None


class StoryPlanOutput(BaseModel):
    """Paths produced by the planner CLI."""

    root: Path
    manifest: Path
    first_scene: Path
    second_scene: Path
    animation: Path
