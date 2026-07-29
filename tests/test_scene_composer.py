from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from engine.scene_composer import (
    build_scene_state,
    load_scene_objects,
    load_scene_spec,
    render_scene_svg,
    resolve_scene_paths,
    validate_composed_scene,
)
from engine.scene_models import SceneObjectSpec, SceneSpec, SceneTransform
from render_scene import main as render_scene_main


def _write_glyphs(path: Path, word: str, count: int = 6) -> None:
    characters = [character for character in word.upper() if character.isalpha()]
    payload = [
        {
            "id": f"source_{index}",
            "object_id": "source",
            "character": characters[index % len(characters)],
            "x": 10.0 + index * 4.0,
            "y": 20.0 + index * 3.0,
            "rotation": float(index),
            "font_size": 8.0 + index,
            "opacity": 0.7,
            "color": "#172033",
            "zone": "mid",
            "layer": "fill",
            "style_role": "fill_mass",
        }
        for index in range(count)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _object(
    identifier: str,
    word: str,
    glyphs_path: Path,
    *,
    z_index: int,
    x: float = 0.0,
    visible: bool = True,
) -> SceneObjectSpec:
    return SceneObjectSpec(
        id=identifier,
        word=word,
        glyphs_path=glyphs_path,
        z_index=z_index,
        visible=visible,
        transform=SceneTransform(x=x, y=12.0, scale_x=0.8, scale_y=0.8),
    )


def test_scene_rejects_duplicate_object_ids(tmp_path: Path) -> None:
    path = tmp_path / "glyphs.json"
    _write_glyphs(path, "CAT")
    first = _object("same", "CAT", path, z_index=1)
    second = _object("same", "MOON", path, z_index=2)

    with pytest.raises(ValidationError):
        SceneSpec(id="duplicate", width=320, height=180, objects=[first, second])


def test_scene_loads_relative_paths_and_orders_by_z_index(tmp_path: Path) -> None:
    _write_glyphs(tmp_path / "cat.json", "CAT")
    _write_glyphs(tmp_path / "moon.json", "MOON")
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(
        json.dumps(
            {
                "id": "cat_moon",
                "width": 640,
                "height": 360,
                "background": "#F4F1EA",
                "objects": [
                    {
                        "id": "cat_01",
                        "word": "CAT",
                        "glyphs_path": "cat.json",
                        "z_index": 3,
                        "transform": {"x": 180, "y": 160},
                    },
                    {
                        "id": "moon_01",
                        "word": "MOON",
                        "glyphs_path": "moon.json",
                        "z_index": 1,
                        "transform": {"x": 460, "y": 45, "scale_x": 0.5, "scale_y": 0.5},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    scene = resolve_scene_paths(load_scene_spec(scene_path), scene_path)
    objects = load_scene_objects(scene)

    assert [item.spec.id for item in objects] == ["moon_01", "cat_01"]
    assert all(item.resolved_path.is_absolute() for item in objects)
    assert {glyph.character for glyph in objects[0].glyphs} <= set("MOON")
    assert {glyph.character for glyph in objects[1].glyphs} <= set("CAT")

    svg = render_scene_svg(scene, objects)
    assert svg.index('id="object_moon_01"') < svg.index('id="object_cat_01"')
    assert 'data-word="MOON"' in svg
    assert 'data-word="CAT"' in svg
    assert 'style="background-color:#F4F1EA"' in svg
    assert "<path" not in svg
    assert "<rect" not in svg

    report = validate_composed_scene(scene, objects, svg)
    assert report["is_valid"] is True
    assert report["object_order"] == ["moon_01", "cat_01"]
    assert report["total_glyph_count"] == 12


def test_transform_changes_keep_local_glyph_state(tmp_path: Path) -> None:
    glyph_path = tmp_path / "cat.json"
    _write_glyphs(glyph_path, "CAT")
    first = _object("cat_01", "CAT", glyph_path, z_index=1, x=30)
    moved = first.model_copy(
        update={
            "transform": SceneTransform(
                x=280,
                y=140,
                scale_x=0.55,
                scale_y=0.55,
                rotation=12,
            )
        }
    )

    first_scene = SceneSpec(id="first", width=400, height=240, objects=[first])
    moved_scene = SceneSpec(id="moved", width=400, height=240, objects=[moved])
    first_loaded = load_scene_objects(first_scene)[0]
    moved_loaded = load_scene_objects(moved_scene)[0]

    assert [glyph.model_dump() for glyph in first_loaded.glyphs] == [
        glyph.model_dump() for glyph in moved_loaded.glyphs
    ]
    assert render_scene_svg(first_scene, [first_loaded]) != render_scene_svg(
        moved_scene, [moved_loaded]
    )


def test_validation_detects_character_from_another_object(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    _write_glyphs(invalid_path, "MOON", count=3)
    scene = SceneSpec(
        id="invalid",
        width=200,
        height=100,
        objects=[_object("cat_01", "CAT", invalid_path, z_index=1)],
    )
    objects = load_scene_objects(scene)
    svg = render_scene_svg(scene, objects)
    report = validate_composed_scene(scene, objects, svg)

    assert report["is_valid"] is False
    assert report["semantic_characters_respected"] is False
    assert report["objects"]["cat_01"]["invalid_glyph_ids"]


def test_hidden_object_is_not_painted_but_remains_in_state(tmp_path: Path) -> None:
    cat_path = tmp_path / "cat.json"
    moon_path = tmp_path / "moon.json"
    _write_glyphs(cat_path, "CAT")
    _write_glyphs(moon_path, "MOON")
    scene = SceneSpec(
        id="hidden",
        width=320,
        height=180,
        objects=[
            _object("cat_01", "CAT", cat_path, z_index=1),
            _object("moon_01", "MOON", moon_path, z_index=2, visible=False),
        ],
    )
    objects = load_scene_objects(scene)
    svg = render_scene_svg(scene, objects)
    state = build_scene_state(scene, objects)
    report = validate_composed_scene(scene, objects, svg)

    assert 'id="object_cat_01"' in svg
    assert 'id="object_moon_01"' not in svg
    assert len(state.objects) == 2
    assert report["visible_object_count"] == 1
    assert report["total_object_count"] == 2


def test_cli_writes_scene_artifacts_without_png(tmp_path: Path) -> None:
    glyph_path = tmp_path / "cat.json"
    _write_glyphs(glyph_path, "CAT")
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(
        json.dumps(
            {
                "id": "cli_scene",
                "width": 320,
                "height": 180,
                "objects": [
                    {
                        "id": "cat_01",
                        "word": "CAT",
                        "glyphs_path": "cat.json",
                        "transform": {"x": 30, "y": 40},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "outputs"

    result = render_scene_main(
        [
            "--scene",
            str(scene_path),
            "--output-dir",
            str(output_dir),
            "--skip-png",
        ]
    )

    generated = output_dir / "cli_scene"
    assert result == 0
    assert (generated / "cli_scene_scene.svg").is_file()
    assert (generated / "cli_scene_scene.json").is_file()
    assert (generated / "cli_scene_validation.json").is_file()
