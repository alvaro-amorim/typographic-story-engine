from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from engine.story_pipeline import StoryPipelineRequest

JobStatus = Literal["queued", "running", "completed", "failed"]
GenerationPreset = Literal["draft", "standard", "quality"]


class StoryJobCreate(BaseModel):
    pipeline: StoryPipelineRequest


class PromptGenerationRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=4000)
    provider: Literal["deterministic", "ollama"] = "deterministic"
    ollama_model: str = "qwen3:4b"
    ollama_url: str = "http://localhost:11434"
    ollama_timeout: float = Field(default=60.0, gt=0.0, le=600.0)
    fallback_to_deterministic: bool = True
    preset: GenerationPreset = "draft"
    duration_seconds: float | None = Field(default=None, gt=0.0, le=60.0)
    fps: int | None = Field(default=None, ge=1, le=60)
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "ease_in_out"
    movement_fraction: float = Field(default=0.28, ge=0.0, le=1.0)
    generate_video: bool = True
    ffmpeg: str | None = None
    video_crf: int | None = Field(default=None, ge=0, le=51)
    video_preset: str | None = None

    @model_validator(mode="after")
    def validate_prompt_request(self) -> "PromptGenerationRequest":
        if not self.prompt.strip():
            raise ValueError("prompt cannot be blank")
        if self.provider == "ollama" and not self.ollama_model.strip():
            raise ValueError("ollama_model is required for the Ollama provider")
        if self.video_preset is not None and not self.video_preset.strip():
            raise ValueError("video_preset cannot be blank")
        return self


class JobCreated(BaseModel):
    id: str
    status: JobStatus
    status_url: str
    studio_url: str | None = None
    video_url: str | None = None


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
