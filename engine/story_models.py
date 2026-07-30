from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MovementDirection = Literal["left", "right", "pose"]


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


class StoryPlanOutput(BaseModel):
    """Paths produced by the planner CLI."""

    root: Path
    manifest: Path
    first_scene: Path
    second_scene: Path
    animation: Path
