from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.story_pipeline import StoryPipelineRequest, run_story_pipeline


def _glyphs(path: Path, word: str) -> None:
    payload = [
        {
            "id": f"glyph_{index}",
            "object_id": "source",
            "character": character,
            "x": 10 + index * 5,
            "y": 20 + index * 3,
            "font_size": 11,
            "opacity": 0.8,
            "color": "#172033",
            "layer": "fill",
            "style_role": "fill_mass",
        }
        for index, character in enumerate(word)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(tmp_path: Path) -> Path:
    _glyphs(tmp_path / "cat.json", "CAT")
    _glyphs(tmp_path / "moon.json", "MOON")
    _glyphs(tmp_path / "ground.json", "GROUND")
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "width": 640,
                "height": 360,
                "background": "#F5F1E8",
                "assets": [
                    {
                        "id": "moon_01",
                        "word": "MOON",
                        "glyphs_path": "moon.json",
                        "aliases": ["moon"],
                        "tags": ["celestial"],
                        "z_index": 1,
                        "transform": {"x": 450, "y": 30},
                    },
                    {
                        "id": "ground_01",
                        "word": "GROUND",
                        "glyphs_path": "ground.json",
                        "aliases": ["ground"],
                        "tags": ["environment"],
                        "always_include": True,
                        "z_index": 2,
                        "transform": {"x": 0, "y": 280},
                    },
                    {
                        "id": "cat_01",
                        "word": "CAT",
                        "glyphs_path": "cat.json",
                        "aliases": ["cat"],
                        "tags": ["subject"],
                        "z_index": 3,
                        "transform": {"x": 120, "y": 180},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_pipeline_generates_plan_and_svg_frames_without_png(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    progress: list[tuple[str, float]] = []
    request = StoryPipelineRequest(
        story="A cat looks at the moon and walks away.",
        registry_path=registry,
        story_id="pipeline_story",
        duration_seconds=1.0,
        fps=2,
        generate_png=False,
        generate_video=False,
    )

    result = run_story_pipeline(
        request,
        tmp_path / "output",
        lambda stage, value: progress.append((stage, value)),
    )

    assert result.story_id == "pipeline_story"
    assert result.planner_provider == "deterministic"
    assert result.frame_count == 3
    assert result.video_path is None
    assert any(path.endswith("pipeline_story_plan.json") for path in result.artifacts)
    assert any(path.endswith("frame_0000.svg") for path in result.artifacts)
    assert any(path.endswith("frame_0002.svg") for path in result.artifacts)
    assert not any(path.endswith(".png") for path in result.artifacts)
    assert progress[0][0] == "loading_registry"
    assert progress[-1] == ("completed", 1.0)


def test_pipeline_request_rejects_video_without_png(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="generate_video requires generate_png"):
        StoryPipelineRequest(
            story="A cat watches the moon.",
            registry_path=tmp_path / "registry.json",
            generate_png=False,
            generate_video=True,
        )


def test_pipeline_request_requires_ollama_model(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="ollama_model is required"):
        StoryPipelineRequest(
            story="A cat watches the moon.",
            registry_path=tmp_path / "registry.json",
            provider="ollama",
            generate_png=False,
        )
