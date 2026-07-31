from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from engine.silhouette_library import build_catalog_masks, load_silhouette_catalog
from examples.build_cat_moon_ground_demo import _render_object

ASSET_CONFIGS = {
    "star_five_point_01": {
        "identifier": "star_01",
        "folder": "star",
        "count": 1400,
        "seed": 4409,
        "font_min": 6,
        "font_max": 17,
        "palette": ["#8B784F", "#B9A36B", "#DAC78E", "#F0E2B5"],
    },
    "cloud_soft_01": {
        "identifier": "cloud_01",
        "folder": "cloud",
        "count": 2200,
        "seed": 5501,
        "font_min": 6,
        "font_max": 18,
        "palette": ["#647184", "#8793A3", "#AEB8C5", "#D7DDE5"],
    },
    "sun_rays_01": {
        "identifier": "sun_01",
        "folder": "sun",
        "count": 2200,
        "seed": 6607,
        "font_min": 6,
        "font_max": 18,
        "palette": ["#9B661F", "#C98A2E", "#E4B64E", "#F1D780"],
    },
    "tree_deciduous_01": {
        "identifier": "tree_01",
        "folder": "tree",
        "count": 3000,
        "seed": 7703,
        "font_min": 6,
        "font_max": 19,
        "palette": ["#24341F", "#3E5632", "#62734B", "#847553"],
    },
    "bird_flying_side_01": {
        "identifier": "bird_01",
        "folder": "bird",
        "count": 2800,
        "seed": 8807,
        "font_min": 6,
        "font_max": 19,
        "palette": ["#172033", "#344966", "#596773", "#8090A0"],
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the approved STAR + CLOUD + SUN + TREE + BIRD glyph assets"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/demo-sky-nature-pack"),
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("assets/catalog.json"),
    )
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.output_dir.resolve()
    if not args.catalog.is_file():
        print(f"Erro: o catálogo de silhuetas '{args.catalog}' não foi encontrado.")
        return 2

    try:
        catalog = load_silhouette_catalog(args.catalog)
        asset_ids = list(ASSET_CONFIGS)
        selected = {asset_id: catalog.get(asset_id) for asset_id in asset_ids}
        masks = build_catalog_masks(
            catalog,
            root / "asset_masks",
            asset_ids=asset_ids,
        )
    except (OSError, ValueError, KeyError) as error:
        print("Erro ao preparar o pacote céu e natureza:")
        print(error)
        return 2

    rendered: dict[str, str] = {}
    for asset_id, config in ASSET_CONFIGS.items():
        asset = selected[asset_id]
        scene_json = _render_object(
            identifier=str(config["identifier"]),
            word=asset.word,
            mask=masks[asset_id],
            count=int(config["count"]),
            seed=int(config["seed"]),
            font_min=float(config["font_min"]),
            font_max=float(config["font_max"]),
            palette=list(config["palette"]),
            output_dir=root / "objects" / str(config["folder"]),
        )
        rendered[str(config["identifier"])] = str(scene_json.resolve())

    _write_json(
        root / "sky_nature_asset_provenance.json",
        {
            "catalog": str(args.catalog.resolve()),
            "assets": {
                str(config["identifier"]): asset_id
                for asset_id, config in ASSET_CONFIGS.items()
            },
            "glyph_state_files": rendered,
        },
    )
    print(f"Pacote céu e natureza pronto em: {root}")
    print("Assets: " + ", ".join(ASSET_CONFIGS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
