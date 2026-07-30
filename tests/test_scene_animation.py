from __future__ import annotations

import json
from pathlib import Path

import pytest

from animate_scenes import main as animate_main
from engine.scene_animation import (
    easing_value,
    frame_count,
    interpolate_scene,
    interpolate_transform,
    iter_animation_frames,
    load_animation_spec,
    prepare_scene_animation,
    resolve_animation_paths,
)
from engine.scene_models import SceneTransform


def _write_glyphs(path: Path, word: str, count: int = 5) -> None:
    characters = [character for character in word if character.isalpha()]
    payload = [
        {
            "id": f"glyph_{index}",
            "object_id": "source",
            "character": characters[index % len(characters)],
            "x": 10 + index * 5,
            "y": 20 + index * 3,
            "font_size": 10 + index,
            "opacity": 0.75,
            "color": "#172033",
            "layer": "fill",
            "style_role": "fill_mass",
        }
        for index in range(count)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_scene(
    path: Path,
    *,
    glyph_path: str,
    word: str = "CAT",
    x: float,
    rotation: float,
    visible: bool = True,
    opacity: float = 1.0,
    z_index: int = 1,
) -> None:
    payload = {
        "id": path.stem,
        "width": 640,
        "height": 360,
        "background": "#F5F1E8",
        "objects": [
            {
                "id": "cat_01",
                "word": word,
                "glyphs_path": glyph_path,
                "z_index": z_index,
                "visible": visible,
                "transform": {
                    "x": x,
                    "y": 120,
                    "scale_x": 0.8,
                    "scale_y": 0.8,
                    "rotation": rotation,
                    "opacity": opacity,
                },
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _animation_file(
    tmp_path: Path,
    *,
    duration: float = 1.0,
    fps: int = 4,
) -> Path:
    glyphs = tmp_path / "cat.json"
    _write_glyphs(glyphs, "CAT")
    start = tmp_path / "start.json"
    end = tmp_path / "end.json"
    _write_scene(start, glyph_path="cat.json", x=20, rotation=170)
    _write_scene(end, glyph_path="cat.json", x=320, rotation=-170)
    animation = tmp_path / "animation.json"
    animation.write_text(
        json.dumps(
            {
                "id": "cat_walk",
                "from_scene": "start.json",
                "to_scene": "end.json",
                "duration_seconds": duration,
                "fps": fps,
                "easing": "ease_in_out",
            }
        ),
        encoding="utf-8",
    )
    return animation


def _prepare(animation_path: Path):
    spec = resolve_animation_paths(load_animation_spec(animation_path), animation_path)
    return prepare_scene_animation(spec)


def test_easing_functions_keep_endpoints() -> None:
    for name in ("linear", "ease_in", "ease_out", "ease_in_out"):
        assert easing_value(name, 0.0) == pytest.approx(0.0)
        assert easing_value(name, 1.0) == pytest.approx(1.0)
    assert easing_value("linear", 0.5) == pytest.approx(0.5)
    assert easing_value("ease_in", 0.5) == pytest.approx(0.25)
    assert easing_value("ease_out", 0.5) == pytest.approx(0.75)
    assert easing_value("ease_in_out", 0.5) == pytest.approx(0.5)


def test_rotation_uses_shortest_axis_path() -> None:
    result = interpolate_transform(
        SceneTransform(rotation=170),
        SceneTransform(rotation=-170),
        0.5,
        start_visible=True,
        end_visible=True,
    )
    assert result.rotation == pytest.approx(180.0)


def test_frame_generation_reuses_local_glyphs(tmp_path: Path) -> None:
    prepared = _prepare(_animation_file(tmp_path))
    frames = list(iter_animation_frames(prepared))

    assert len(frames) == frame_count(prepared.spec) == 5
    assert frames[0].state.progress == pytest.approx(0.0)
    assert frames[-1].state.progress == pytest.approx(1.0)
    assert frames[0].scene.objects[0].transform.x == pytest.approx(20)
    assert frames[-1].scene.objects[0].transform.x == pytest.approx(320)
    assert frames[0].objects[0].glyphs is prepared.source_objects[0].glyphs
    assert frames[-1].objects[0].glyphs is prepared.source_objects[0].glyphs
    assert all(frame.validation["is_valid"] for frame in frames)


def test_visibility_change_is_implemented_as_opacity(tmp_path: Path) -> None:
    glyphs = tmp_path / "cat.json"
    _write_glyphs(glyphs, "CAT")
    start = tmp_path / "start.json"
    end = tmp_path / "end.json"
    _write_scene(start, glyph_path="cat.json", x=10, rotation=0, visible=False)
    _write_scene(end, glyph_path="cat.json", x=10, rotation=0, visible=True)
    animation = tmp_path / "animation.json"
    animation.write_text(
        json.dumps(
            {
                "id": "fade_in",
                "from_scene": "start.json",
                "to_scene": "end.json",
                "duration_seconds": 1,
                "fps": 2,
            }
        ),
        encoding="utf-8",
    )
    prepared = _prepare(animation)
    first, middle, last = list(iter_animation_frames(prepared))

    assert first.scene.objects[0].visible is True
    assert first.scene.objects[0].transform.opacity == pytest.approx(0.0)
    assert 0.0 < middle.scene.objects[0].transform.opacity < 1.0
    assert last.scene.objects[0].transform.opacity == pytest.approx(1.0)


def test_incompatible_semantic_word_is_rejected(tmp_path: Path) -> None:
    glyphs = tmp_path / "cat.json"
    _write_glyphs(glyphs, "CAT")
    start = tmp_path / "start.json"
    end = tmp_path / "end.json"
    _write_scene(start, glyph_path="cat.json", word="CAT", x=0, rotation=0)
    _write_scene(end, glyph_path="cat.json", word="DOG", x=100, rotation=0)
    animation = tmp_path / "animation.json"
    animation.write_text(
        json.dumps(
            {
                "id": "invalid",
                "from_scene": "start.json",
                "to_scene": "end.json",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="changes semantic word"):
        _prepare(animation)


def test_cli_generates_svg_frames_and_manifest(tmp_path: Path) -> None:
    animation = _animation_file(tmp_path, duration=1.0, fps=3)
    output = tmp_path / "output"

    result = animate_main(
        [
            "--animation",
            str(animation),
            "--output-dir",
            str(output),
            "--skip-png",
        ]
    )

    root = output / "cat_walk"
    svg_frames = sorted((root / "frames" / "svg").glob("*.svg"))
    manifest = json.loads(
        (root / "cat_walk_manifest.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (root / "cat_walk_validation.json").read_text(encoding="utf-8")
    )

    assert result == 0
    assert len(svg_frames) == 4
    assert manifest["frame_count"] == 4
    assert report["is_valid"] is True
    assert report["glyphs_reused_per_frame"] == 5
