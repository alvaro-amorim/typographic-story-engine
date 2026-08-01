from __future__ import annotations

from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator

from engine.story_pipeline import StoryPipelineRequest

JobStatus = Literal["queued", "running", "completed", "failed"]
GenerationPreset = Literal["draft", "standard", "quality"]


class StoryJobCreate(BaseModel):
    pipeline: StoryPipelineRequest


class OllamaConnectionRequest(BaseModel):
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = Field(default=2.0, gt=0.0, le=600.0)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP(S) URL")
        return normalized


class OllamaModelTestRequest(OllamaConnectionRequest):
    model: str = Field(min_length=1, max_length=200)
    timeout_seconds: float = Field(default=60.0, gt=0.0, le=600.0)

    @field_validator("model")
    @classmethod
    def normalize_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("model cannot be blank")
        return normalized


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
    planner_error: str | None = None
    frame_count: int | None = None
    artifacts: list[str] = Field(default_factory=list)
    video_path: str | None = None
    error: str | None = None


class ArtifactList(BaseModel):
    job_id: str
    artifacts: list[str]
