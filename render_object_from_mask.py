from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import fmean
from typing import Sequence

from pydantic import ValidationError

from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    distribute_glyphs,
)
from engine.image_analysis import analyze_mask
from engine.models import SemanticObject
from engine.png_exporter import export_to_png
from engine.semantic_validation import validate_scene
from engine.svg_renderer import render_to_svg

DEFAULT_PALETTE = ["#2C303A", "#4F5D75", "#BFC0C0", "#EAE2B7"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Typographic Story Engine - strict typographic SVG renderer"
    )
    parser.add_argument("--id", default="obj_01", help="Unique object ID")
    parser.add_argument("--word", required=True, help="Word used to build the object")
    parser.add_argument("--mask", type=Path, required=True, help="Path to a PNG mask")
    parser.add_argument("--count", type=int, default=12000, help="Number of glyphs")
    parser.add_argument("--font-min", type=float, default=8.0, help="Minimum font size")
    parser.add_argument("--font-max", type=float, default=28.0, help="Maximum font size")
    parser.add_argument(
        "--rotation-min",
        type=float,
        default=-12.0,
        help="Minimum fallback rotation when local orientation is unavailable",
    )
    parser.add_argument(
        "--rotation-max",
        type=float,
        default=12.0,
        help="Maximum fallback rotation when local orientation is unavailable",
    )
    parser.add_argument(
        "--palette",
        nargs="+",
        default=DEFAULT_PALETTE,
        metavar="HEX",
        help="One or more six-digit hexadecimal colors",
    )
    parser.add_argument(
        "--seed", type=int, default=817392, help="Seed used for deterministic rendering"
    )
    parser.add_argument(
        "--edge-threshold",
        type=float,
        default=0.18,
        help="Maximum normalized depth classified as edge",
    )
    parser.add_argument(
        "--mid-threshold",
        type=float,
        default=0.55,
        help="Maximum normalized depth classified as middle zone",
    )
    parser.add_argument(
        "--edge-ratio",
        type=float,
        default=0.45,
        help="Relative glyph budget assigned to the edge",
    )
    parser.add_argument(
        "--mid-ratio",
        type=float,
        default=0.35,
        help="Relative glyph budget assigned to the middle zone",
    )
    parser.add_argument(
        "--core-ratio",
        type=float,
        default=0.20,
        help="Relative glyph budget assigned to the core",
    )
    parser.add_argument(
        "--cell-size",
        type=int,
        default=8,
        help="Spatial occupancy grid cell size in mask pixels",
    )
    parser.add_argument(
        "--edge-capacity",
        type=int,
        default=4,
        help="Maximum initial glyph occupancy per edge cell",
    )
    parser.add_argument(
        "--mid-capacity",
        type=int,
        default=3,
        help="Maximum initial glyph occupancy per middle cell",
    )
    parser.add_argument(
        "--core-capacity",
        type=int,
        default=2,
        help="Maximum initial glyph occupancy per core cell",
    )
    parser.add_argument(
        "--orientation-mode",
        choices=("tangent", "random"),
        default="tangent",
        help="Align glyphs with local curvature or keep random rotations",
    )
    parser.add_argument(
        "--orientation-smoothing",
        type=float,
        default=1.25,
        help="Gaussian smoothing applied before estimating local tangents",
    )
    parser.add_argument(
        "--orientation-jitter",
        type=float,
        default=6.0,
        help="Maximum organic rotation jitter around the local tangent",
    )
    parser.add_argument(
        "--edge-orientation-strength",
        type=float,
        default=0.92,
        help="How strongly edge glyphs follow local curvature",
    )
    parser.add_argument(
        "--mid-orientation-strength",
        type=float,
        default=0.72,
        help="How strongly middle glyphs follow local curvature",
    )
    parser.add_argument(
        "--core-orientation-strength",
        type=float,
        default=0.38,
        help="How strongly core glyphs follow local curvature",
    )
    parser.add_argument(
        "--orientation-min-confidence",
        type=float,
        default=0.05,
        help="Minimum tangent confidence before using curvature alignment",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory used for generated artifacts",
    )
    parser.add_argument(
        "--skip-png",
        action="store_true",
        help="Skip PNG preview generation",
    )
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.mask.is_file():
        print(f"Erro: a máscara '{args.mask}' não foi encontrada ou não é um arquivo.")
        return 2

    try:
        target_object = SemanticObject(
            id=args.id,
            word=args.word,
            mask_path=str(args.mask),
            glyph_count=args.count,
            font_size_range=(args.font_min, args.font_max),
            palette=args.palette,
            seed=args.seed,
        )
        distribution_config = DistributionConfig(
            edge_threshold=args.edge_threshold,
            mid_threshold=args.mid_threshold,
            edge_ratio=args.edge_ratio,
            mid_ratio=args.mid_ratio,
            core_ratio=args.core_ratio,
            cell_size=args.cell_size,
            edge_capacity=args.edge_capacity,
            mid_capacity=args.mid_capacity,
            core_capacity=args.core_capacity,
        )
        orientation_config = OrientationConfig(
            enabled=args.orientation_mode == "tangent",
            edge_strength=args.edge_orientation_strength,
            mid_strength=args.mid_orientation_strength,
            core_strength=args.core_orientation_strength,
            jitter_degrees=args.orientation_jitter,
            min_confidence=args.orientation_min_confidence,
        )
    except (ValidationError, ValueError) as error:
        print("Erro de configuração:")
        print(error)
        return 2

    print(
        f"Iniciando Typographic Story Engine: renderizando "
        f"'{target_object.word}' com seed {target_object.seed}..."
    )

    try:
        analysis = analyze_mask(
            target_object.mask_path,
            orientation_smoothing=args.orientation_smoothing,
        )
        scene_glyphs = distribute_glyphs(
            object_id=target_object.id,
            valid_coords=analysis.valid_coordinates,
            character_sequence=target_object.character_sequence,
            glyph_count=target_object.glyph_count,
            font_size_range=target_object.font_size_range,
            palette=target_object.palette,
            seed=target_object.seed,
            rotation_range=(args.rotation_min, args.rotation_max),
            distribution_config=distribution_config,
            orientation_field=(
                analysis.tangent_field
                if orientation_config.enabled
                else None
            ),
            orientation_config=orientation_config,
        )
    except (OSError, ValueError) as error:
        print(f"Erro durante a geração: {error}")
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = target_object.id
    svg_path = args.output_dir / f"{base_name}_scene.svg"
    json_path = args.output_dir / f"{base_name}_scene.json"
    report_path = args.output_dir / f"{base_name}_validation.json"
    png_path = args.output_dir / f"{base_name}_preview.png"

    svg_output = render_to_svg(
        scene_glyphs,
        width=analysis.width,
        height=analysis.height,
    )
    svg_path.write_text(svg_output, encoding="utf-8")
    _write_json(json_path, [glyph.model_dump() for glyph in scene_glyphs])

    zone_counts = Counter(glyph.zone for glyph in scene_glyphs)
    orientation_counts = Counter(
        glyph.orientation_source for glyph in scene_glyphs
    )
    tangent_confidences = [
        glyph.orientation_confidence
        for glyph in scene_glyphs
        if glyph.orientation_source == "tangent"
    ]

    report = validate_scene(
        scene_glyphs,
        target_object.allowed_characters,
        svg_output,
    )
    report["seed"] = target_object.seed
    report["word"] = target_object.word
    report["character_sequence"] = list(target_object.character_sequence)
    report["distribution"] = asdict(distribution_config)
    report["zone_counts"] = {
        zone: zone_counts.get(zone, 0) for zone in ("edge", "mid", "core")
    }
    report["orientation"] = {
        **asdict(orientation_config),
        "mode": args.orientation_mode,
        "smoothing": args.orientation_smoothing,
    }
    report["orientation_counts"] = {
        source: orientation_counts.get(source, 0)
        for source in ("tangent", "random")
    }
    report["mean_tangent_confidence"] = (
        fmean(tangent_confidences) if tangent_confidences else 0.0
    )
    _write_json(report_path, report)

    if not report["is_valid"]:
        print(f"Validação reprovada. Consulte: {report_path}")
        return 1

    if not args.skip_png:
        try:
            export_to_png(svg_output, str(png_path))
        except Exception as error:
            print(f"Aviso: não foi possível gerar a prévia PNG: {error}")
            return 1

    print("Validação aprovada: SVG estrito e caracteres semânticos corretos.")
    print(
        "Distribuição por zona: "
        f"edge={zone_counts.get('edge', 0)}, "
        f"mid={zone_counts.get('mid', 0)}, "
        f"core={zone_counts.get('core', 0)}"
    )
    print(
        "Orientação: "
        f"tangent={orientation_counts.get('tangent', 0)}, "
        f"random={orientation_counts.get('random', 0)}"
    )
    print(f"Artefatos gerados em: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
