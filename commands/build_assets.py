from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.silhouette_library import build_catalog_masks, load_silhouette_catalog


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate curated silhouette SVGs and build binary PNG masks"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("assets/catalog.json"),
        help="Path to the curated silhouette catalog",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/_asset_cache"),
        help="Destination for generated PNG masks",
    )
    parser.add_argument(
        "--asset",
        action="append",
        dest="asset_ids",
        help="Build only this asset ID. Repeat the option for multiple assets.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.catalog.is_file():
        print(f"Erro: o catálogo '{args.catalog}' não foi encontrado.")
        return 2

    try:
        catalog = load_silhouette_catalog(args.catalog)
        built = build_catalog_masks(
            catalog,
            args.output_dir,
            asset_ids=args.asset_ids,
        )
    except (OSError, ValueError, KeyError, ValidationError) as error:
        print("Erro ao construir a biblioteca de máscaras:")
        print(error)
        return 2

    print(f"Máscaras construídas: {len(built)}")
    for asset_id, path in sorted(built.items()):
        print(f"  {asset_id}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
