from __future__ import annotations

import json
from pathlib import Path

import pytest

from engine.asset_registry import (
    load_asset_registry,
    normalize_story_text,
    resolve_registry_paths,
)
from engine.scene_animation import (
    iter_animation_frames,
    prepare_scene_animation,
    resolve_animation_paths,
)
from engine.story_planner import plan_story, write_story_plan
from plan_story import main as plan_story_main


def _write_glyphs(path: Path, word: str, count: int = 6) -> None:
    characters = [character for character in word if character.isalpha()]
    payload = [
        {
            "id": f"glyph_{index}",
            "object_id": "source",
            "character": characters[index % len(characters)],
            "x": 10 + index * 4,
            "y": 20 + index * 2,
            "font_size": 9 + index,
            "opacity": 0.75,
            "color": "#172033",
            "layer": "fill",
            "style_role": "fill_mass",
        }
        for index in range(count)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(tmp_path: Path) -> Path:
    _write_glyphs(tmp_path / "cat.json", "CAT")
    _write_glyphs(tmp_path / "moon.json", "MOON")
    _write_glyphs(tmp_path / "ground.json", "GROUND")
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "id": "demo",
                "width": 1000,
                "height": 600,
                "background": "#F5F1E8",
                "assets": [
                    {
                        "id": "moon_01",
                        "word": "MOON",
                        "glyphs_path": "moon.json",
                        "aliases": ["moon", "lua"],
                        "tags": ["celestial", "background"],
                        "z_index": 1,
                        "transform": {"x": 720, "y": 50, "scale_x": 0.6, "scale_y": 0.6},
                    },
                    {
                        "id": "ground_01",
                        "word": "GROUND",
                        "glyphs_path": "ground.json",
                        "aliases": ["ground", "chão"],
                        "tags": ["ground", "environment"],
                        "always_include": True,
                        "z_index": 2,
                        "transform": {"x": 0, "y": 480, "scale_x": 1.5, "scale_y": 1.0},
                    },
                    {
                        "id": "cat_01",
                        "word": "CAT",
                        "glyphs_path": "cat.json",
                        "aliases": ["cat", "gato"],
                        "tags": ["subject", "animal"],
                        "z_index": 3,
                        "transform": {"x": 220, "y": 250, "scale_x": 0.8, "scale_y": 0.8},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_path


def _loaded_registry(tmp_path: Path):
    path = _registry(tmp_path)
    return path, resolve_registry_paths(load_asset_registry(path), path)


def test_text_normalization_handles_accents_and_punctuation() -> None:
    assert normalize_story_text("O GATO olha para a LUA!") == "o gato olha para a lua"
    assert normalize_story_text("Caminha para a esquerda.") == "caminha para a esquerda"


def test_story_plan_is_deterministic_and_moves_subject_right(tmp_path: Path) -> None:
    registry_path, registry = _loaded_registry(tmp_path)
    story = "A cat looks at the moon and then walks away."

    first = plan_story(story, registry, registry_file=str(registry_path))
    second = plan_story(story, registry, registry_file=str(registry_path))

    assert first.manifest == second.manifest
    assert first.first_scene == second.first_scene
    assert first.second_scene == second.second_scene
    assert first.manifest.movement_direction == "right"
    assert first.manifest.included_asset_ids == ["moon_01", "ground_01", "cat_01"]
    assert first.manifest.movement_distance == pytest.approx(280.0)

    start = {item.id: item for item in first.first_scene.objects}["cat_01"]
    end = {item.id: item for item in first.second_scene.objects}["cat_01"]
    assert end.transform.x == pytest.approx(start.transform.x + 280.0)
    assert end.transform.scale_x < start.transform.scale_x


def test_portuguese_left_movement_uses_aliases(tmp_path: Path) -> None:
    _, registry = _loaded_registry(tmp_path)
    bundle = plan_story(
        "O gato olha para a lua e caminha para a esquerda.",
        registry,
        story_id="gato_esquerda",
    )

    start = {item.id: item for item in bundle.first_scene.objects}["cat_01"]
    end = {item.id: item for item in bundle.second_scene.objects}["cat_01"]
    assert bundle.manifest.subject_asset_id == "cat_01"
    assert bundle.manifest.movement_direction == "left"
    assert end.transform.x < start.transform.x


def test_non_movement_story_produces_pose_transition(tmp_path: Path) -> None:
    _, registry = _loaded_registry(tmp_path)
    bundle = plan_story("A cat watches the moon.", registry)

    start = {item.id: item for item in bundle.first_scene.objects}["cat_01"]
    end = {item.id: item for item in bundle.second_scene.objects}["cat_01"]
    assert bundle.manifest.movement_direction == "pose"
    assert bundle.manifest.movement_distance == 0.0
    assert end.transform.x == start.transform.x
    assert end.transform.rotation == pytest.approx(start.transform.rotation - 3.0)


def test_unsupported_subject_is_rejected(tmp_path: Path) -> None:
    _, registry = _loaded_registry(tmp_path)
    with pytest.raises(ValueError, match="no supported subject"):
        plan_story("A dog runs under the moon.", registry)


def test_written_plan_is_directly_accepted_by_animator(tmp_path: Path) -> None:
    registry_path, registry = _loaded_registry(tmp_path)
    bundle = plan_story(
        "A cat walks away from the moon.",
        registry,
        story_id="direct_pipeline",
        duration_seconds=1.0,
        fps=3,
        registry_file=str(registry_path),
    )
    output = write_story_plan(bundle, tmp_path / "plans")
    animation = resolve_animation_paths(bundle.animation, output.animation)
    prepared = prepare_scene_animation(animation)
    frames = list(iter_animation_frames(prepared))

    assert len(frames) == 4
    assert all(frame.validation["is_valid"] for frame in frames)
    assert prepared.object_ids == ("moon_01", "ground_01", "cat_01")


def test_cli_writes_plan_artifacts(tmp_path: Path) -> None:
    registry_path = _registry(tmp_path)
    output_dir = tmp_path / "output"

    result = plan_story_main(
        [
            "--story",
            "A cat looks at the moon and walks away.",
            "--registry",
            str(registry_path),
            "--id",
            "cli_story",
            "--duration",
            "1",
            "--fps",
            "4",
            "--output-dir",
            str(output_dir),
        ]
    )

    root = output_dir / "cli_story"
    manifest = json.loads((root / "cli_story_plan.json").read_text(encoding="utf-8"))
    assert result == 0
    assert (root / "cli_story_scene_001.json").is_file()
    assert (root / "cli_story_scene_002.json").is_file()
    assert (root / "cli_story_animation.json").is_file()
    assert manifest["subject_asset_id"] == "cat_01"
    assert manifest["movement_direction"] == "right"
