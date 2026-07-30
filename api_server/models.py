from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from engine.story_pipeline import StoryPipelineRequest

JobStatus = Literal["queued", "running", "completed", "failed"]


class StoryJobCreate(BaseModel):
    pipeline: StoryPipelineRequest


class JobCreated(BaseModel):
    id: str
    status: JobStatus
    status_url: str


class JobRecord(BaseModel):
    id: str
    status: JobStatus
    stage: str
    progress: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime
    request: StoryPipelineRequest
    story_id: str | None = None
    planner_provider: str | None = None
    planner_fallback_used: bool = False
    frame_count: int | None = None
    artifacts: list[str] = Field(default_factory=list)
    video_path: str | None = None
    error: str | None = None


class ArtifactList(BaseModel):
    job_id: str
    artifacts: list[str]
