from __future__ import annotations

from dataclasses import asdict, dataclass

from api_server.models import GenerationPreset, PromptGenerationRequest
from engine.story_pipeline import StoryPipelineRequest


@dataclass(frozen=True)
class PresetConfig:
    label: str
    description: str
    duration_seconds: float
    fps: int
    video_crf: int
    video_preset: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


PRESETS: dict[GenerationPreset, PresetConfig] = {
    "draft": PresetConfig(
        label="Rascunho rápido",
        description="Poucos frames e codificação ultrarrápida para testar ideias.",
        duration_seconds=1.0,
        fps=6,
        video_crf=28,
        video_preset="ultrafast",
    ),
    "standard": PresetConfig(
        label="Padrão",
        description="Equilíbrio entre velocidade, fluidez e tamanho do arquivo.",
        duration_seconds=2.0,
        fps=12,
        video_crf=20,
        video_preset="veryfast",
    ),
    "quality": PresetConfig(
        label="Qualidade",
        description="Mais frames e compressão mais cuidadosa para revisão visual.",
        duration_seconds=4.0,
        fps=24,
        video_crf=18,
        video_preset="medium",
    ),
}


def build_pipeline_request(
    request: PromptGenerationRequest,
    registry_path,
) -> StoryPipelineRequest:
    preset = PRESETS[request.preset]
    return StoryPipelineRequest(
        story=request.prompt.strip(),
        registry_path=registry_path,
        provider=request.provider,
        ollama_model=(request.ollama_model if request.provider == "ollama" else None),
        ollama_url=request.ollama_url,
        ollama_timeout=request.ollama_timeout,
        fallback_to_deterministic=request.fallback_to_deterministic,
        duration_seconds=request.duration_seconds or preset.duration_seconds,
        fps=request.fps or preset.fps,
        easing=request.easing,
        movement_fraction=request.movement_fraction,
        generate_png=True,
        generate_video=request.generate_video,
        ffmpeg=request.ffmpeg,
        video_crf=(
            request.video_crf if request.video_crf is not None else preset.video_crf
        ),
        video_preset=request.video_preset or preset.video_preset,
    )
