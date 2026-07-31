from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

import pytest

from engine.asset_registry import (
    load_asset_registry,
    resolve_registry_paths,
)
from engine.scene_composer import load_scene_objects, render_scene_svg
from engine.scene_models import SceneObjectSpec, SceneSpec, SceneTransform
from engine.spatial_planner import (
    parse_spatial_relations,
    transformed_bounds,
)
from engine.story_planner import plan_story


def _write_glyphs(path: Path, word: str, *, width: int = 100, height: int = 60) -> None:
    characters = list(word)
    payload = []
    for index, character in enumerate(characters * 3):
        payload.append(
            {
                "id": f"glyph_{index:03d}",
                "object_id": "source",
                "character": character,
                "x": 10 + (index % len(characters)) * (width / max(1, len(characters) - 1)),
                "y": 10 + (index // len(characters)) * (height / 2),
                "font_size": 10,
                "opacity": 0.8,
                "color": "#172033",
                "layer": "fill",
                "style_role": "fill_mass",
            }
        )
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(tmp_path: Path):
    _write_glyphs(tmp_path / "bird.json", "BIRD", width=120, height=55)
    _write_glyphs(tmp_path / "cloud.json", "CLOUD", width=180, height=70)
    _write_glyphs(tmp_path / "moon.json", "MOON", width=120, height=120)
    _write_glyphs(tmp_path / "ground.json", "GROUND", width=500, height=35)
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "id": "spatial-demo",
                "width": 1000,
                "height": 600,
                "background": "#F5F1E8",
                "assets": [
                    {
                        "id": "moon_01",
                        "word": "MOON",
                        "glyphs_path": "moon.json",
                        "aliases": ["moon", "lua"],
                        "tags": ["celestial"],
                        "z_index": 1,
                        "transform": {"x": 700, "y": 40, "scale_x": 0.8, "scale_y": 0.8},
                    },
                    {
                        "id": "cloud_01",
                        "word": "CLOUD",
                        "glyphs_path": "cloud.json",
                        "aliases": ["cloud", "nuvem"],
                        "tags": ["weather"],
                        "z_index": 2,
                        "transform": {"x": 420, "y": 180, "scale_x": 0.7, "scale_y": 0.7},
                    },
                    {
                        "id": "ground_01",
                        "word": "GROUND",
                        "glyphs_path": "ground.json",
                        "aliases": ["ground", "chao"],
                        "tags": ["ground"],
                        "always_include": True,
                        "z_index": 3,
                        "transform": {"x": 0, "y": 520, "scale_x": 1.6, "scale_y": 1.0},
                    },
                    {
                        "id": "bird_01",
                        "word": "BIRD",
                        "glyphs_path": "bird.json",
                        "aliases": ["bird", "passaro"],
                        "tags": ["subject", "animal", "aerial"],
                        "facing": "right",
                        "z_index": 4,
                        "transform": {"x": 180, "y": 260, "scale_x": 0.65, "scale_y": 0.65},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return resolve_registry_paths(load_asset_registry(path), path)


def test_parser_extracts_chained_portuguese_and_english_relations(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    relations = parse_spatial_relations(
        "A bird flies above a cloud under the moon.",
        registry.assets,
    )

    assert [relation.model_dump() for relation in relations] == [
        {
            "subject_asset_id": "bird_01",
            "relation": "above",
            "reference_asset_id": "cloud_01",
        },
        {
            "subject_asset_id": "cloud_01",
            "relation": "below",
            "reference_asset_id": "moon_01",
        },
    ]

    portuguese = parse_spatial_relations(
        "Um pássaro voa acima de uma nuvem sob a lua.",
        registry.assets,
    )
    assert [item.relation for item in portuguese] == ["above", "below"]


def test_story_layout_uses_measured_bounds_and_faces_movement(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    bundle = plan_story(
        "A bird flies left above a cloud under the moon.",
        registry,
        story_id="bird_spatial",
    )

    start = {item.id: item for item in bundle.first_scene.objects}
    end = {item.id: item for item in bundle.second_scene.objects}
    assets = registry.by_id()

    bird_bounds = transformed_bounds(assets["bird_01"], start["bird_01"].transform)
    cloud_bounds = transformed_bounds(assets["cloud_01"], start["cloud_01"].transform)
    moon_bounds = transformed_bounds(assets["moon_01"], start["moon_01"].transform)

    assert bird_bounds.bottom < cloud_bounds.top
    assert cloud_bounds.center_y > moon_bounds.center_y
    assert start["bird_01"].transform.mirror_x is True
    assert end["bird_01"].transform.mirror_x is True
    assert end["bird_01"].transform.x < start["bird_01"].transform.x
    assert bundle.manifest.subject_source_facing == "right"
    assert bundle.manifest.subject_mirrored is True
    assert len(bundle.manifest.spatial_relations) == 2


def test_rightward_subject_keeps_source_facing(tmp_path: Path) -> None:
    registry = _registry(tmp_path)
    bundle = plan_story("A bird flies right above a cloud.", registry)
    bird = {item.id: item for item in bundle.first_scene.objects}["bird_01"]

    assert bird.transform.mirror_x is False
    assert bundle.manifest.subject_mirrored is False


def test_mirroring_reflects_positions_without_mirroring_text(tmp_path: Path) -> None:
    glyphs = tmp_path / "pair.json"
    glyphs.write_text(
        json.dumps(
            [
                {
                    "id": "left",
                    "object_id": "source",
                    "character": "C",
                    "x": 10,
                    "y": 20,
                    "rotation": 12,
                    "font_size": 10,
                    "opacity": 1,
                    "color": "#172033",
                    "layer": "fill",
                    "style_role": "fill_mass",
                },
                {
                    "id": "right",
                    "object_id": "source",
                    "character": "A",
                    "x": 30,
                    "y": 20,
                    "rotation": -8,
                    "font_size": 10,
                    "opacity": 1,
                    "color": "#172033",
                    "layer": "fill",
                    "style_role": "fill_mass",
                },
            ]
        ),
        encoding="utf-8",
    )
    scene = SceneSpec(
        id="mirror_test",
        width=100,
        height=80,
        objects=[
            SceneObjectSpec(
                id="cat_01",
                word="CAT",
                glyphs_path=glyphs,
                transform=SceneTransform(mirror_x=True),
            )
        ],
    )
    objects = load_scene_objects(scene)
    svg = render_scene_svg(scene, objects)
    root = ElementTree.fromstring(svg)
    texts = {element.text: element.attrib["transform"] for element in root.iter() if element.tag.endswith("text")}

    assert texts["C"].startswith("translate(30.000 20.000) rotate(-12.000)")
    assert texts["A"].startswith("translate(10.000 20.000) rotate(8.000)")
    assert "scale(-" not in svg
    assert 'data-mirror-x="true"' in svg
