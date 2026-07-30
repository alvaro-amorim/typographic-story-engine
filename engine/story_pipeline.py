from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field, model_validator

from engine.animation_models import AnimationManifest
from engine.asset_registry import load_asset_registry, resolve_registry_paths
from engine.planner_providers import (
    DeterministicPlannerProvider,
    OllamaPlannerProvider,
    plan_story_with_provider,
)
from engine.png_exporter import export_to_png
from engine.scene_animation import (
    frame_count,
    iter_animation_frames,
    prepare_scene_animation,
    resolve_animation_paths,
)
from engine.story_planner import write_story_plan
from engine.video_export import export_png_sequence_to_mp4

ProgressCallback = Callable[[str, float], None]


class StoryPipelineRequest(BaseModel):
    story: str = Field(min_length=1)
    registry_path: Path
    story_id: str | None = None
    provider: Literal["deterministic", "ollama"] = "deterministic"
    ollama_model: str | None = None
    ollama_url: str = "http://localhost:11434"
    ollama_timeout: float = Field(default=60.0, gt=0.0)
    fallback_to_deterministic: bool = True
    duration_seconds: float = Field(default=2.0, gt=0.0, le=60.0)
    fps: int = Field(default=12, ge=1, le=60)
    easing: Literal["linear", "ease_in", "ease_out", "ease_in_out"] = "ease_in_out"
    movement_fraction: float = Field(default=0.28, ge=0.0, le=1.0)
    generate_png: bool = True
    generate_video: bool = False
    ffmpeg: str | None = None
    video_crf: int = Field(default=18, ge=0, le=51)
    video_preset: str = "medium"

    @model_validator(mode="after")
    def validate_provider_and_video(self) -> "StoryPipelineRequest":
        if self.provider == "ollama" and not self.ollama_model:
            raise ValueError("ollama_model is required for the Ollama provider")
        if self.generate_video and not self.generate_png:
            raise ValueError("generate_video requires generate_png")
        if not self.video_preset.strip():
            raise ValueError("video_preset cannot be blank")
        return self


class StoryPipelineResult(BaseModel):
    story_id: str
    root: Path
    planner_provider: str
    planner_fallback_used: bool
    frame_count: int
    artifacts: list[str]
    video_path: str | None = None


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _provider(request: StoryPipelineRequest):
    if request.provider == "deterministic":
        return DeterministicPlannerProvider(
            movement_fraction=request.movement_fraction
        )
    return OllamaPlannerProvider(
        model=request.ollama_model or "",
        base_url=request.ollama_url,
        timeout_seconds=request.ollama_timeout,
        movement_fraction=request.movement_fraction,
    )


def _artifacts(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file()
    )


def run_story_pipeline(
    request: StoryPipelineRequest,
    output_root: str | Path,
    progress: ProgressCallback | None = None,
) -> StoryPipelineResult:
    callback = progress or (lambda stage, value: None)
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    callback("loading_registry", 0.03)
    registry_path = request.registry_path.resolve()
    if not registry_path.is_file():
        raise ValueError(f"asset registry was not found: {registry_path}")
    registry = resolve_registry_paths(
        load_asset_registry(registry_path),
        registry_path,
    )

    callback("planning", 0.08)
    bundle = plan_story_with_provider(
        request.story,
        registry,
        _provider(request),
        story_id=request.story_id,
        duration_seconds=request.duration_seconds,
        fps=request.fps,
        easing=request.easing,
        registry_file=str(registry_path),
        fallback_to_deterministic=request.fallback_to_deterministic,
        fallback_movement_fraction=request.movement_fraction,
    )
    plan_output = write_story_plan(bundle, root / "plans")

    callback("preparing_animation", 0.14)
    animation_spec = resolve_animation_paths(bundle.animation, plan_output.animation)
    prepared = prepare_scene_animation(animation_spec)
    transition_root = root / "animation" / animation_spec.id
    svg_dir = transition_root / "frames" / "svg"
    png_dir = transition_root / "frames" / "png"
    svg_dir.mkdir(parents=True, exist_ok=True)
    if request.generate_png:
        png_dir.mkdir(parents=True, exist_ok=True)

    total = frame_count(animation_spec)
    padding = max(4, len(str(total - 1)))
    frame_states = []
    invalid_frames: list[int] = []
    for frame in iter_animation_frames(prepared):
        name = f"frame_{frame.state.index:0{padding}d}"
        (svg_dir / f"{name}.svg").write_text(frame.svg, encoding="utf-8")
        if request.generate_png:
            export_to_png(frame.svg, str(png_dir / f"{name}.png"))
        if not frame.validation["is_valid"]:
            invalid_frames.append(frame.state.index)
        frame_states.append(frame.state)
        callback(
            "generating_frames",
            0.15 + 0.70 * ((frame.state.index + 1) / total),
        )

    animation_manifest = AnimationManifest(
        id=animation_spec.id,
        duration_seconds=animation_spec.duration_seconds,
        fps=animation_spec.fps,
        easing=animation_spec.easing,
        frame_count=len(frame_states),
        from_scene=str(prepared.from_scene_path),
        to_scene=str(prepared.to_scene_path),
        object_ids=list(prepared.object_ids),
        frames=frame_states,
    )
    animation_report = {
        "is_valid": not invalid_frames and len(frame_states) == total,
        "expected_frame_count": total,
        "generated_frame_count": len(frame_states),
        "invalid_frames": invalid_frames,
        "object_ids": list(prepared.object_ids),
        "glyphs_reused_per_frame": sum(
            len(item.glyphs) for item in prepared.source_objects
        ),
        "png_exported": request.generate_png,
    }
    _write_json(
        transition_root / f"{animation_spec.id}_manifest.json",
        animation_manifest.model_dump(mode="json"),
    )
    _write_json(
        transition_root / f"{animation_spec.id}_validation.json",
        animation_report,
    )
    if not animation_report["is_valid"]:
        raise RuntimeError(
            f"animation validation failed for frames: {invalid_frames}"
        )

    video_path: Path | None = None
    if request.generate_video:
        callback("exporting_video", 0.90)
        video_path = root / f"{bundle.manifest.id}.mp4"
        export_png_sequence_to_mp4(
            frames_dir=png_dir,
            output_path=video_path,
            fps=request.fps,
            ffmpeg=request.ffmpeg,
            crf=request.video_crf,
            preset=request.video_preset,
        )

    callback("completed", 1.0)
    return StoryPipelineResult(
        story_id=bundle.manifest.id,
        root=root,
        planner_provider=bundle.manifest.planner_provider,
        planner_fallback_used=bundle.manifest.planner_fallback_used,
        frame_count=len(frame_states),
        artifacts=_artifacts(root),
        video_path=(
            str(video_path.relative_to(root)).replace("\\", "/")
            if video_path is not None
            else None
        ),
    )
