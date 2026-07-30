from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from animate_scenes import main as animate_main
from examples.build_cat_moon_ground_demo import main as build_scene_demo


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build two CAT + MOON + GROUND scenes and interpolate them"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-cat-walk"),
    )
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--skip-png", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()

    scene_result = build_scene_demo(
        [
            "--output-dir",
            str(root),
            "--skip-png",
        ]
    )
    if scene_result != 0:
        return scene_result

    start_scene_path = root / "cat_moon_ground_scene.json"
    start_payload = json.loads(start_scene_path.read_text(encoding="utf-8"))
    start_payload["id"] = "cat_walk_start"
    start_scene_path = root / "cat_walk_start.json"
    start_scene_path.write_text(
        json.dumps(start_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    end_payload = json.loads(json.dumps(start_payload))
    end_payload["id"] = "cat_walk_end"
    for item in end_payload["objects"]:
        if item["id"] == "cat_01":
            item["transform"].update(
                {
                    "x": 735,
                    "y": 270,
                    "scale_x": 0.82,
                    "scale_y": 0.82,
                    "rotation": -4,
                }
            )
        elif item["id"] == "moon_01":
            item["transform"].update(
                {
                    "x": 870,
                    "rotation": -3,
                }
            )
    end_scene_path = root / "cat_walk_end.json"
    end_scene_path.write_text(
        json.dumps(end_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    animation_payload = {
        "id": "cat_walk_01",
        "from_scene": str(start_scene_path),
        "to_scene": str(end_scene_path),
        "duration_seconds": args.duration,
        "fps": args.fps,
        "easing": "ease_in_out",
    }
    animation_path = root / "cat_walk_animation.json"
    animation_path.write_text(
        json.dumps(animation_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    animation_arguments = [
        "--animation",
        str(animation_path),
        "--output-dir",
        str(root / "animation"),
    ]
    if args.skip_png:
        animation_arguments.append("--skip-png")

    result = animate_main(animation_arguments)
    if result == 0:
        print(f"Demo de animação completo em: {root}")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
