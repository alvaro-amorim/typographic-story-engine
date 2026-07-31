from __future__ import annotations

import threading
from pathlib import Path

from examples.build_cat_moon_ground_demo import main as build_assets_demo
from examples.build_sky_nature_asset_pack import main as build_sky_nature_pack
from examples.build_story_video_demo import _write_registry

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDIO_ROOT = REPOSITORY_ROOT / "outputs" / "_studio" / "default-assets"
DEFAULT_CAT_ASSET = "cat_walking_side_01"

_BOOTSTRAP_LOCK = threading.RLock()


def registry_is_ready(root: str | Path = DEFAULT_STUDIO_ROOT) -> bool:
    target = Path(root).resolve()
    required = (
        target / "asset_registry.json",
        target / "objects" / "cat" / "cat_01_scene.json",
        target / "objects" / "moon" / "moon_01_scene.json",
        target / "objects" / "ground" / "ground_01_scene.json",
        target / "objects" / "star" / "star_01_scene.json",
        target / "objects" / "cloud" / "cloud_01_scene.json",
        target / "objects" / "sun" / "sun_01_scene.json",
        target / "objects" / "tree" / "tree_01_scene.json",
        target / "objects" / "bird" / "bird_01_scene.json",
    )
    return all(path.is_file() for path in required)


def ensure_default_registry(
    root: str | Path = DEFAULT_STUDIO_ROOT,
    *,
    cat_asset: str = DEFAULT_CAT_ASSET,
    force: bool = False,
) -> Path:
    target = Path(root).resolve()
    with _BOOTSTRAP_LOCK:
        if not force and registry_is_ready(target):
            return target / "asset_registry.json"

        arguments = [
            "--output-dir", str(target),
            "--cat-asset", cat_asset,
            "--skip-png",
            "--clean",
        ]
        result = build_assets_demo(arguments)
        if result != 0:
            raise RuntimeError(
                f"default studio base asset build failed with exit code {result}"
            )

        pack_result = build_sky_nature_pack(["--output-dir", str(target)])
        if pack_result != 0:
            raise RuntimeError(
                f"default studio sky/nature build failed with exit code {pack_result}"
            )

        registry = _write_registry(target, cat_asset)
        if not registry_is_ready(target):
            raise RuntimeError("default studio registry is incomplete after bootstrap")
        return registry.resolve()
