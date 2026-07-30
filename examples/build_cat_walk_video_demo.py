from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from examples.build_cat_walk_animation_demo import main as build_animation_demo
from export_video import main as export_video_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the CAT walk animation and export the first MP4"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-cat-walk-video"),
    )
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--ffmpeg", default=None)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()

    animation_result = build_animation_demo(
        [
            "--output-dir",
            str(root),
            "--duration",
            str(args.duration),
            "--fps",
            str(args.fps),
        ]
    )
    if animation_result != 0:
        return animation_result

    frames_dir = root / "animation" / "cat_walk_01" / "frames" / "png"
    output_path = root / "cat_walk_01.mp4"
    export_arguments = [
        "--frames-dir",
        str(frames_dir),
        "--output",
        str(output_path),
        "--fps",
        str(args.fps),
        "--crf",
        str(args.crf),
        "--preset",
        args.preset,
    ]
    if args.ffmpeg:
        export_arguments.extend(["--ffmpeg", args.ffmpeg])

    result = export_video_main(export_arguments)
    if result == 0:
        print(f"Vertical slice concluído: {output_path}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
