from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api_server.app import create_app
from api_server.studio_assets import registry_is_ready
from engine.asset_registry import AssetRegistry, AssetSpec
from engine.scene_models import SceneTransform
from engine.silhouette_library import load_silhouette_catalog, validate_silhouette_svg
from engine.story_planner import deterministic_story_decision


NEW_ASSET_IDS = {
    "star_five_point_01",
    "cloud_soft_01",
    "sun_rays_01",
    "tree_deciduous_01",
    "bird_flying_side_01",
}


def test_catalog_contains_sky_and_nature_pack() -> None:
    catalog = load_silhouette_catalog(Path("assets/catalog.json"))
    identifiers = {asset.id for asset in catalog.assets}

    assert NEW_ASSET_IDS.issubset(identifiers)
    assert catalog.get_default("bird.flight").id == "bird_flying_side_01"
    assert catalog.get_default("environment.star").word == "STAR"
    assert catalog.get_default("environment.cloud").word == "CLOUD"
    assert catalog.get_default("environment.sun").word == "SUN"
    assert catalog.get_default("environment.tree").word == "TREE"

    for asset_id in NEW_ASSET_IDS:
        asset = catalog.get(asset_id)
        report = validate_silhouette_svg(asset.source_svg)
        assert report["is_valid"] is True
        assert asset.license.spdx == "CC0-1.0"


def _planner_registry(tmp_path: Path) -> AssetRegistry:
    glyphs = tmp_path / "glyphs.json"
    glyphs.write_text("{}", encoding="utf-8")
    return AssetRegistry(
        id="sky-pack-test",
        assets=[
            AssetSpec(
                id="ground_01",
                word="GROUND",
                glyphs_path=glyphs,
                aliases=["ground", "chão"],
                tags={"environment", "ground"},
                always_include=True,
            ),
            AssetSpec(
                id="cloud_01",
                word="CLOUD",
                glyphs_path=glyphs,
                aliases=["cloud", "nuvem"],
                tags={"environment", "weather"},
            ),
            AssetSpec(
                id="bird_01",
                word="BIRD",
                glyphs_path=glyphs,
                aliases=["bird", "pássaro", "passaro", "ave"],
                tags={"subject", "animal", "aerial"},
                transform=SceneTransform(x=100, y=100),
            ),
        ],
    )


def test_portuguese_bird_prompt_selects_subject_cloud_and_left_flight(
    tmp_path: Path,
) -> None:
    decision = deterministic_story_decision(
        "Um pássaro voa para a esquerda acima de uma nuvem.",
        _planner_registry(tmp_path),
    )

    assert decision.subject_asset_id == "bird_01"
    assert set(decision.included_asset_ids) == {"bird_01", "cloud_01", "ground_01"}
    assert decision.movement_direction == "left"


def test_english_bird_prompt_recognizes_default_flight_movement(tmp_path: Path) -> None:
    decision = deterministic_story_decision(
        "A bird flies above a cloud.",
        _planner_registry(tmp_path),
    )

    assert decision.subject_asset_id == "bird_01"
    assert decision.movement_direction == "right"


def test_registry_readiness_requires_complete_expanded_pack(tmp_path: Path) -> None:
    required = [
        "asset_registry.json",
        "objects/cat/cat_01_scene.json",
        "objects/moon/moon_01_scene.json",
        "objects/ground/ground_01_scene.json",
        "objects/star/star_01_scene.json",
        "objects/cloud/cloud_01_scene.json",
        "objects/sun/sun_01_scene.json",
        "objects/tree/tree_01_scene.json",
        "objects/bird/bird_01_scene.json",
    ]
    for relative in required[:-1]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    assert registry_is_ready(tmp_path) is False

    final = tmp_path / required[-1]
    final.parent.mkdir(parents=True, exist_ok=True)
    final.write_text("{}", encoding="utf-8")
    assert registry_is_ready(tmp_path) is True


def test_capabilities_exposes_registry_assets_to_studio(tmp_path: Path) -> None:
    glyphs = tmp_path / "bird.json"
    glyphs.write_text("{}", encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "id": "browser-test",
                "assets": [
                    {
                        "id": "bird_01",
                        "word": "BIRD",
                        "glyphs_path": str(glyphs),
                        "aliases": ["bird", "pássaro"],
                        "tags": ["subject", "animal"],
                    },
                    {
                        "id": "cloud_01",
                        "word": "CLOUD",
                        "glyphs_path": str(glyphs),
                        "aliases": ["cloud", "nuvem"],
                        "tags": ["environment", "weather"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    client = TestClient(
        create_app(
            output_root=tmp_path / "jobs",
            default_registry_path=registry,
        )
    )
    capabilities = client.get("/v1/capabilities")

    assert capabilities.status_code == 200
    payload = capabilities.json()
    assert payload["asset_words"] == ["BIRD", "CLOUD"]
    assert [asset["id"] for asset in payload["assets"]] == ["bird_01", "cloud_01"]
    assert payload["assets"][0]["kind"] == "subject"
    assert payload["assets"][1]["kind"] == "environment"
    assert client.get("/static/asset-browser.js").status_code == 200
    assert client.get("/static/asset-browser.css").status_code == 200
