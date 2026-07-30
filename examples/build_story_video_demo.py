from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from animate_scenes import main as animate_main
from examples.build_cat_moon_ground_demo import main as build_assets_demo
from export_video import main as export_video_main
from plan_story import main as plan_story_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a short CAT story into scenes, frames and an optional MP4"
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
    registry = {
        "id": "cat_moon_ground_demo",
        "width": 1280,
        "height": 720,
        "background": "#F5F1E8",
        "assets": [
            {
                "id": "moon_01",
                "word": "MOON",
                "glyphs_path": str(
                    (root / "objects" / "moon" / "moon_01_scene.json").resolve()
                ),
                "aliases": ["moon", "lua"],
                "tags": ["celestial", "background"],
                "z_index": 1,
                "transform": {
                    "x": 900,
                    "y": 45,
                    "scale_x": 0.62,
                    "scale_y": 0.62,
                    "rotation": -7,
                },
            },
            {
                "id": "ground_01",
                "word": "GROUND",
                "glyphs_path": str(
                    (root / "objects" / "ground" / "ground_01_scene.json").resolve()
                ),
                "aliases": ["ground", "chão", "chao"],
                "tags": ["ground", "environment"],
                "always_include": True,
                "z_index": 2,
                "transform": {
                    "x": -15,
                    "y": 565,
                    "scale_x": 1.25,
                    "scale_y": 0.60,
                },
            },
            {
                "id": "cat_01",
                "word": "CAT",
                "glyphs_path": str(
                    (root / "objects" / "cat" / "cat_01_scene.json").resolve()
                ),
                "aliases": ["cat", "gato"],
                "tags": ["subject", "animal", "approved-pose", cat_asset],
                "z_index": 3,
                "transform": {
                    "x": 360,
                    "y": 215,
                    "scale_x": 0.72,
                    "scale_y": 0.72,
                    "rotation": 0,
                },
            },
        ],
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

    registry_path = _write_registry(root, args.cat_asset)
    plan_arguments = [
        "--story",
        args.story,
        "--registry",
        str(registry_path),
        "--id",
        args.id,
        "--duration",
        str(args.duration),
        "--fps",
        str(args.fps),
        "--provider",
        args.provider,
        "--output-dir",
        str(root / "plans"),
    ]
    if args.provider == "ollama":
        if args.ollama_model:
            plan_arguments.extend(["--ollama-model", args.ollama_model])
        plan_arguments.extend(
            [
                "--ollama-url",
                args.ollama_url,
                "--ollama-timeout",
                str(args.ollama_timeout),
            ]
        )
    if args.no_fallback:
        plan_arguments.append("--no-fallback")

    plan_result = plan_story_main(plan_arguments)
    if plan_result != 0:
        return plan_result

    plan_root = root / "plans" / args.id
    animation_file = plan_root / f"{args.id}_animation.json"
    animation_arguments = [
        "--animation",
        str(animation_file),
        "--output-dir",
        str(root / "animation"),
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
        "--frames-dir",
        str(frames_dir),
        "--output",
        str(video_path),
        "--fps",
        str(args.fps),
        "--crf",
        str(args.crf),
        "--preset",
        args.preset,
    ]
    if args.ffmpeg:
        export_arguments.extend(["--ffmpeg", args.ffmpeg])
    video_result = export_video_main(export_arguments)
    if video_result == 0:
        print(f"Story vertical slice completed: {video_path}")
    return video_result


if __name__ == "__main__":
    raise SystemExit(main())
