from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from animate_scenes import main as animate_main
from examples.build_cat_moon_ground_demo import main as build_assets_demo
from examples.build_sky_nature_asset_pack import main as build_sky_nature_pack
from export_video import main as export_video_main
from plan_story import main as plan_story_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a short typographic story into scenes, frames and an optional MP4"
    )
    parser.add_argument(
        "--story",
        default="A cat looks at the moon and then walks away.",
    )
    parser.add_argument("--id", default="cat_story_01")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-story-video"),
    )
    parser.add_argument(
        "--cat-asset",
        default="cat_walking_side_01",
        help="Approved cat silhouette. The walking pose is the motion-story default.",
    )
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument(
        "--provider",
        choices=("deterministic", "ollama"),
        default="deterministic",
    )
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--ollama-timeout", type=float, default=60.0)
    parser.add_argument("--no-fallback", action="store_true")
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument(
        "--skip-video",
        action="store_true",
        help="Generate story, scenes and SVG frames without PNG or FFmpeg",
    )
    return parser


def _write_registry(root: Path, cat_asset: str) -> Path:
    def glyphs(folder: str, identifier: str) -> Path:
        return (root / "objects" / folder / f"{identifier}_scene.json").resolve()

    assets: list[dict[str, object]] = []

    def add(
        *,
        identifier: str,
        word: str,
        folder: str,
        aliases: list[str],
        tags: list[str],
        z_index: int,
        transform: dict[str, float],
        always_include: bool = False,
        facing: str = "neutral",
    ) -> None:
        path = glyphs(folder, identifier)
        if not path.is_file():
            return
        payload: dict[str, object] = {
            "id": identifier,
            "word": word,
            "glyphs_path": str(path),
            "aliases": aliases,
            "tags": tags,
            "z_index": z_index,
            "transform": transform,
            "facing": facing,
        }
        if always_include:
            payload["always_include"] = True
        assets.append(payload)

    add(
        identifier="moon_01",
        word="MOON",
        folder="moon",
        aliases=["moon", "lua"],
        tags=["celestial", "background", "night"],
        z_index=1,
        transform={"x": 900, "y": 45, "scale_x": 0.62, "scale_y": 0.62, "rotation": -7},
    )
    add(
        identifier="star_01",
        word="STAR",
        folder="star",
        aliases=["star", "stars", "estrela", "estrelas"],
        tags=["celestial", "background", "night"],
        z_index=1,
        transform={"x": 730, "y": 70, "scale_x": 0.30, "scale_y": 0.30, "rotation": 8},
    )
    add(
        identifier="sun_01",
        word="SUN",
        folder="sun",
        aliases=["sun", "sol", "sunrise", "nascer do sol"],
        tags=["celestial", "background", "day"],
        z_index=1,
        transform={"x": 930, "y": 35, "scale_x": 0.48, "scale_y": 0.48, "rotation": 0},
    )
    add(
        identifier="cloud_01",
        word="CLOUD",
        folder="cloud",
        aliases=["cloud", "clouds", "nuvem", "nuvens"],
        tags=["sky", "weather", "background"],
        z_index=2,
        transform={"x": 500, "y": 80, "scale_x": 0.55, "scale_y": 0.42, "rotation": -2},
    )
    add(
        identifier="ground_01",
        word="GROUND",
        folder="ground",
        aliases=["ground", "chão", "chao"],
        tags=["ground", "environment"],
        always_include=True,
        z_index=3,
        transform={"x": -15, "y": 565, "scale_x": 1.25, "scale_y": 0.60},
    )
    add(
        identifier="tree_01",
        word="TREE",
        folder="tree",
        aliases=["tree", "trees", "árvore", "árvores", "arvore", "arvores"],
        tags=["nature", "foreground", "environment"],
        z_index=4,
        transform={"x": 70, "y": 265, "scale_x": 0.68, "scale_y": 0.68, "rotation": 0},
    )
    add(
        identifier="cat_01",
        word="CAT",
        folder="cat",
        aliases=["cat", "gato"],
        tags=["subject", "animal", "approved-pose", cat_asset],
        z_index=5,
        transform={"x": 360, "y": 215, "scale_x": 0.72, "scale_y": 0.72, "rotation": 0},
        facing="right",
    )
    add(
        identifier="bird_01",
        word="BIRD",
        folder="bird",
        aliases=["bird", "birds", "pássaro", "pássaros", "passaro", "passaros", "ave", "aves"],
        tags=["subject", "animal", "aerial", "approved-pose", "bird_flying_side_01"],
        z_index=5,
        transform={"x": 260, "y": 145, "scale_x": 0.42, "scale_y": 0.42, "rotation": -3},
        facing="right",
    )

    registry = {
        "id": "typographic_story_studio_default",
        "width": 1280,
        "height": 720,
        "background": "#F5F1E8",
        "assets": assets,
    }
    path = root / "asset_registry.json"
    path.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()

    assets_result = build_assets_demo(
        [
            "--output-dir",
            str(root),
            "--cat-asset",
            args.cat_asset,
            "--skip-png",
        ]
    )
    if assets_result != 0:
        return assets_result

    pack_result = build_sky_nature_pack(["--output-dir", str(root)])
    if pack_result != 0:
        return pack_result

    registry_path = _write_registry(root, args.cat_asset)
    plan_arguments = [
        "--story", args.story,
        "--registry", str(registry_path),
        "--id", args.id,
        "--duration", str(args.duration),
        "--fps", str(args.fps),
        "--provider", args.provider,
        "--output-dir", str(root / "plans"),
    ]
    if args.provider == "ollama":
        if args.ollama_model:
            plan_arguments.extend(["--ollama-model", args.ollama_model])
        plan_arguments.extend(
            ["--ollama-url", args.ollama_url, "--ollama-timeout", str(args.ollama_timeout)]
        )
    if args.no_fallback:
        plan_arguments.append("--no-fallback")

    plan_result = plan_story_main(plan_arguments)
    if plan_result != 0:
        return plan_result

    plan_root = root / "plans" / args.id
    animation_file = plan_root / f"{args.id}_animation.json"
    animation_arguments = [
        "--animation", str(animation_file),
        "--output-dir", str(root / "animation"),
    ]
    if args.skip_video:
        animation_arguments.append("--skip-png")
    animation_result = animate_main(animation_arguments)
    if animation_result != 0:
        return animation_result

    transition_id = f"{args.id}_transition_001"
    if args.skip_video:
        print(f"Story vertical slice without MP4 completed in: {root}")
        return 0

    frames_dir = root / "animation" / transition_id / "frames" / "png"
    video_path = root / f"{args.id}.mp4"
    export_arguments = [
        "--frames-dir", str(frames_dir),
        "--output", str(video_path),
        "--fps", str(args.fps),
        "--crf", str(args.crf),
        "--preset", args.preset,
    ]
    if args.ffmpeg:
        export_arguments.extend(["--ffmpeg", args.ffmpeg])
    video_result = export_video_main(export_arguments)
    if video_result == 0:
        print(f"Story vertical slice completed: {video_path}")
    return video_result


if __name__ == "__main__":
    raise SystemExit(main())
