from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from engine.silhouette_library import (
    build_catalog_masks,
    load_silhouette_catalog,
    validate_silhouette_svg,
)
from examples.build_cat_moon_ground_demo import build_parser as build_scene_parser
from examples.build_story_video_demo import build_parser as build_story_parser


def test_project_catalog_contains_curated_baseline_assets() -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))

    identifiers = {asset.id for asset in catalog.assets}
    assert {
        "cat_standing_side_01",
        "cat_sitting_side_01",
        "cat_walking_side_01",
        "moon_crescent_01",
        "ground_hill_01",
    }.issubset(identifiers)
    assert all(asset.source_svg.is_file() for asset in catalog.assets)
    assert all(asset.license.spdx == "CC0-1.0" for asset in catalog.assets)


def test_catalog_records_approved_cat_pose_defaults() -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))

    sitting = catalog.get_default("cat.contemplative")
    walking = catalog.get_default("cat.locomotion")
    standing = catalog.get_default("cat.neutral")

    assert sitting.id == "cat_sitting_side_01"
    assert sitting.status == "primary"
    assert "default-scene" in sitting.roles

    assert walking.id == "cat_walking_side_01"
    assert walking.status == "primary"
    assert "default-motion" in walking.roles

    assert standing.id == "cat_standing_side_01"
    assert standing.status == "secondary"


def test_catalog_prepares_sitting_to_walking_sequence_without_claiming_it_is_ready() -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))
    sequence = catalog.get_pose_sequence("cat_sitting_to_walking_01")

    assert sequence.from_asset == "cat_sitting_side_01"
    assert sequence.to_asset == "cat_walking_side_01"
    assert sequence.intent == "leave_scene"
    assert sequence.status == "planned"


def test_demo_defaults_match_approved_visual_roles() -> None:
    scene_args = build_scene_parser().parse_args([])
    story_args = build_story_parser().parse_args([])

    assert scene_args.cat_asset == "cat_sitting_side_01"
    assert story_args.cat_asset == "cat_walking_side_01"


def test_catalog_builds_strict_binary_masks(tmp_path: Path) -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))
    built = build_catalog_masks(
        catalog,
        tmp_path,
        asset_ids=["cat_standing_side_01", "moon_crescent_01"],
    )

    assert set(built) == {"cat_standing_side_01", "moon_crescent_01"}
    for path in built.values():
        assert path.is_file()
        with Image.open(path) as image:
            values = set(image.convert("L").getdata())
        assert values == {0, 255}


def test_svg_validation_rejects_external_resources(tmp_path: Path) -> None:
    source = tmp_path / "unsafe.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<image href="https://example.com/image.png" width="10" height="10"/>'
        "</svg>",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported SVG element|external resources"):
        validate_silhouette_svg(source)


def test_unknown_asset_id_is_rejected(tmp_path: Path) -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))

    with pytest.raises(KeyError, match="unknown silhouette assets"):
        build_catalog_masks(catalog, tmp_path, asset_ids=["invented_asset"])
