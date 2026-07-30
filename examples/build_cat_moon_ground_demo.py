from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from commands.clean_outputs import clean_outputs
from engine.silhouette_library import build_catalog_masks, load_silhouette_catalog
from render_object_from_mask import main as render_object_main
from render_scene import main as render_scene_main


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the curated CAT + MOON + GROUND multi-object scene"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-cat-moon-ground"),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("assets/catalog.json"),
    )
    parser.add_argument(
        "--cat-asset",
        default="cat_sitting_side_01",
        help="Approved cat silhouette. The contemplative sitting pose is the scene default.",
    )
    parser.add_argument("--moon-asset", default="moon_crescent_01")
    parser.add_argument("--ground-asset", default="ground_hill_01")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--skip-png", action="store_true")
    return parser


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


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()
    if args.clean:
        clean_outputs(root)

    if not args.catalog.is_file():
        print(f"Erro: o catálogo de silhuetas '{args.catalog}' não foi encontrado.")
        return 2

    catalog = load_silhouette_catalog(args.catalog)
    selected_ids = [args.cat_asset, args.moon_asset, args.ground_asset]
    try:
        selected = {asset_id: catalog.get(asset_id) for asset_id in selected_ids}
        masks = build_catalog_masks(
            catalog,
            root / "asset_masks",
            asset_ids=selected_ids,
        )
    except (OSError, ValueError, KeyError) as error:
        print("Erro ao preparar as silhuetas aprovadas:")
        print(error)
        return 2

    objects = root / "objects"
    scene_dir = root / "scene"
    objects.mkdir(parents=True, exist_ok=True)

    cat_json = _render_object(
        identifier="cat_01",
        word=selected[args.cat_asset].word,
        mask=masks[args.cat_asset],
        count=3200,
        seed=1103,
        font_min=7,
        font_max=22,
        palette=["#12151D", "#29303D", "#50596A", "#7A8190"],
        output_dir=objects / "cat",
    )
    moon_json = _render_object(
        identifier="moon_01",
        word=selected[args.moon_asset].word,
        mask=masks[args.moon_asset],
        count=2400,
        seed=2207,
        font_min=7,
        font_max=21,
        palette=["#7A715D", "#A99A76", "#D3C6A1", "#F0E6C8"],
        output_dir=objects / "moon",
    )
    ground_json = _render_object(
        identifier="ground_01",
        word=selected[args.ground_asset].word,
        mask=masks[args.ground_asset],
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
                "word": selected[args.moon_asset].word,
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
                "word": selected[args.ground_asset].word,
                "glyphs_path": str(ground_json),
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
                "word": selected[args.cat_asset].word,
                "glyphs_path": str(cat_json),
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
    scene_path = root / "cat_moon_ground_scene.json"
    _write_json(scene_path, scene_payload)
    _write_json(
        root / "asset_provenance.json",
        {
            "catalog": str(args.catalog.resolve()),
            "objects": {
                "cat_01": args.cat_asset,
                "moon_01": args.moon_asset,
                "ground_01": args.ground_asset,
            },
        },
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
    print("Assets: " + ", ".join(selected_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
