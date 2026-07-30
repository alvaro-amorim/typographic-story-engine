from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw

from render_object_from_mask import main as render_object_main
from render_scene import main as render_scene_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the first CAT + MOON + GROUND multi-object scene"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-cat-moon-ground"),
    )
    parser.add_argument("--skip-png", action="store_true")
    return parser


def _save_cat_mask(path: Path) -> None:
    image = Image.new("L", (360, 360), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((85, 130, 280, 330), fill=0)
    draw.ellipse((115, 45, 255, 190), fill=0)
    draw.polygon(((125, 75), (145, 8), (180, 70)), fill=0)
    draw.polygon(((195, 68), (235, 8), (245, 84)), fill=0)
    draw.rounded_rectangle((105, 280, 155, 355), radius=18, fill=0)
    draw.rounded_rectangle((205, 280, 255, 355), radius=18, fill=0)
    draw.line((95, 235, 30, 200, 18, 135), fill=0, width=32)
    draw.ellipse((8, 108, 50, 155), fill=0)
    image.save(path)


def _save_moon_mask(path: Path) -> None:
    image = Image.new("L", (320, 320), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((20, 20, 300, 300), fill=0)
    draw.ellipse((105, -8, 330, 270), fill=255)
    image.save(path)


def _save_ground_mask(path: Path) -> None:
    image = Image.new("L", (720, 120), 255)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((8, 35, 712, 112), radius=28, fill=0)
    image.save(path)


def _render_object(
    *,
    identifier: str,
    word: str,
    mask: Path,
    count: int,
    seed: int,
    font_min: float,
    font_max: float,
    palette: list[str],
    output_dir: Path,
) -> Path:
    arguments = [
        "--id",
        identifier,
        "--word",
        word,
        "--mask",
        str(mask),
        "--count",
        str(count),
        "--seed",
        str(seed),
        "--font-min",
        str(font_min),
        "--font-max",
        str(font_max),
        "--output-dir",
        str(output_dir),
        "--palette",
        *palette,
        "--skip-png",
    ]
    result = render_object_main(arguments)
    if result != 0:
        raise RuntimeError(f"object renderer failed for {identifier} with code {result}")
    return output_dir / f"{identifier}_scene.json"


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()
    masks = root / "masks"
    objects = root / "objects"
    scene_dir = root / "scene"
    masks.mkdir(parents=True, exist_ok=True)
    objects.mkdir(parents=True, exist_ok=True)

    cat_mask = masks / "cat.png"
    moon_mask = masks / "moon.png"
    ground_mask = masks / "ground.png"
    _save_cat_mask(cat_mask)
    _save_moon_mask(moon_mask)
    _save_ground_mask(ground_mask)

    cat_json = _render_object(
        identifier="cat_01",
        word="CAT",
        mask=cat_mask,
        count=3200,
        seed=1103,
        font_min=7,
        font_max=22,
        palette=["#12151D", "#29303D", "#50596A", "#7A8190"],
        output_dir=objects / "cat",
    )
    moon_json = _render_object(
        identifier="moon_01",
        word="MOON",
        mask=moon_mask,
        count=2400,
        seed=2207,
        font_min=7,
        font_max=21,
        palette=["#7A715D", "#A99A76", "#D3C6A1", "#F0E6C8"],
        output_dir=objects / "moon",
    )
    ground_json = _render_object(
        identifier="ground_01",
        word="GROUND",
        mask=ground_mask,
        count=3000,
        seed=3301,
        font_min=6,
        font_max=16,
        palette=["#27351F", "#445A32", "#6F7541", "#8C8050"],
        output_dir=objects / "ground",
    )

    scene_payload = {
        "id": "cat_moon_ground_01",
        "width": 1280,
        "height": 720,
        "background": "#F5F1E8",
        "objects": [
            {
                "id": "moon_01",
                "word": "MOON",
                "glyphs_path": str(moon_json),
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
                "glyphs_path": str(ground_json),
                "z_index": 2,
                "transform": {
                    "x": -15,
                    "y": 565,
                    "scale_x": 1.82,
                    "scale_y": 1.05,
                },
            },
            {
                "id": "cat_01",
                "word": "CAT",
                "glyphs_path": str(cat_json),
                "z_index": 3,
                "transform": {
                    "x": 390,
                    "y": 255,
                    "scale_x": 0.88,
                    "scale_y": 0.88,
                    "rotation": 2,
                },
            },
        ],
    }
    scene_path = root / "cat_moon_ground_scene.json"
    scene_path.write_text(
        json.dumps(scene_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    scene_arguments = [
        "--scene",
        str(scene_path),
        "--output-dir",
        str(scene_dir),
    ]
    if args.skip_png:
        scene_arguments.append("--skip-png")
    result = render_scene_main(scene_arguments)
    if result != 0:
        return result

    print(f"Demo completo em: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
