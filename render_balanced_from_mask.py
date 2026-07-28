from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import fmean
from typing import Sequence

from pydantic import ValidationError

from engine.balanced_styling import (
    BalancedStyleConfig,
    STYLE_ROLE_ORDER,
    distribute_balanced_glyphs,
    summarize_balanced_metrics,
)
from engine.glyph_distribution import DistributionConfig, OrientationConfig
from engine.image_analysis import analyze_mask
from engine.layered_distribution import summarize_layer_metrics
from engine.models import SemanticObject
from engine.png_exporter import export_to_png
from engine.semantic_validation import validate_scene
from engine.svg_renderer import render_to_svg

DEFAULT_PALETTE = ["#2C303A", "#4F5D75", "#BFC0C0", "#EAE2B7"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Typographic Story Engine - controlled organic balance renderer"
    )
    parser.add_argument("--id", default="obj_01", help="Unique object ID")
    parser.add_argument("--word", required=True, help="Word used to build the object")
    parser.add_argument("--mask", type=Path, required=True, help="Path to a PNG mask")
    parser.add_argument("--count", type=int, default=12000, help="Number of glyphs")
    parser.add_argument("--font-min", type=float, default=8.0)
    parser.add_argument("--font-max", type=float, default=28.0)
    parser.add_argument("--rotation-min", type=float, default=-12.0)
    parser.add_argument("--rotation-max", type=float, default=12.0)
    parser.add_argument(
        "--palette",
        nargs="+",
        default=DEFAULT_PALETTE,
        metavar="HEX",
    )
    parser.add_argument("--seed", type=int, default=817392)

    parser.add_argument("--outline-ratio", type=float, default=0.34)
    parser.add_argument("--fill-ratio", type=float, default=0.56)
    parser.add_argument("--texture-ratio", type=float, default=0.10)
    parser.add_argument("--outline-shadow-fraction", type=float, default=0.26)
    parser.add_argument("--outline-detail-depth-max", type=float, default=0.105)
    parser.add_argument("--outline-shadow-depth-min", type=float, default=0.050)
    parser.add_argument("--outline-depth-max", type=float, default=0.18)
    parser.add_argument("--fill-depth-min", type=float, default=0.035)
    parser.add_argument("--texture-depth-min", type=float, default=0.24)
    parser.add_argument("--organic-scale", type=float, default=0.032)
    parser.add_argument("--outline-coherence", type=float, default=0.48)
    parser.add_argument("--fill-modulation-strength", type=float, default=0.12)
    parser.add_argument("--fill-opacity-min", type=float, default=0.42)
    parser.add_argument("--fill-opacity-max", type=float, default=0.57)
    parser.add_argument("--fill-dark-probability", type=float, default=0.08)
    parser.add_argument("--texture-opacity-min", type=float, default=0.21)
    parser.add_argument("--texture-opacity-max", type=float, default=0.28)

    parser.add_argument("--edge-threshold", type=float, default=0.18)
    parser.add_argument("--mid-threshold", type=float, default=0.55)
    parser.add_argument("--orientation-smoothing", type=float, default=2.0)
    parser.add_argument("--orientation-jitter", type=float, default=7.0)
    parser.add_argument("--edge-orientation-strength", type=float, default=0.90)
    parser.add_argument("--mid-orientation-strength", type=float, default=0.48)
    parser.add_argument("--core-orientation-strength", type=float, default=0.12)
    parser.add_argument("--orientation-min-confidence", type=float, default=0.14)
    parser.add_argument("--orientation-confidence-power", type=float, default=1.60)

    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--skip-png", action="store_true")
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
        distribution = DistributionConfig(
            edge_threshold=args.edge_threshold,
            mid_threshold=args.mid_threshold,
        )
        orientation = OrientationConfig(
            enabled=True,
            adaptive=True,
            edge_strength=args.edge_orientation_strength,
            mid_strength=args.mid_orientation_strength,
            core_strength=args.core_orientation_strength,
            jitter_degrees=args.orientation_jitter,
            min_confidence=args.orientation_min_confidence,
            confidence_power=args.orientation_confidence_power,
        )
        style = BalancedStyleConfig(
            outline_ratio=args.outline_ratio,
            fill_ratio=args.fill_ratio,
            texture_ratio=args.texture_ratio,
            outline_shadow_fraction=args.outline_shadow_fraction,
            outline_detail_depth_max=args.outline_detail_depth_max,
            outline_shadow_depth_min=args.outline_shadow_depth_min,
            outline_depth_max=args.outline_depth_max,
            fill_depth_min=args.fill_depth_min,
            texture_depth_min=args.texture_depth_min,
            organic_scale=args.organic_scale,
            outline_coherence=args.outline_coherence,
            fill_modulation_strength=args.fill_modulation_strength,
            fill_opacity_min=args.fill_opacity_min,
            fill_opacity_max=args.fill_opacity_max,
            fill_dark_probability=args.fill_dark_probability,
            texture_opacity_min=args.texture_opacity_min,
            texture_opacity_max=args.texture_opacity_max,
        )
    except (ValidationError, ValueError) as error:
        print("Erro de configuração:")
        print(error)
        return 2

    print(
        f"Iniciando renderer balanceado para '{target_object.word}' "
        f"com seed {target_object.seed}..."
    )
    try:
        analysis = analyze_mask(
            target_object.mask_path,
            orientation_smoothing=args.orientation_smoothing,
        )
        glyphs = distribute_balanced_glyphs(
            object_id=target_object.id,
            valid_coords=analysis.valid_coordinates,
            character_sequence=target_object.character_sequence,
            glyph_count=target_object.glyph_count,
            font_size_range=target_object.font_size_range,
            palette=target_object.palette,
            seed=target_object.seed,
            rotation_range=(args.rotation_min, args.rotation_max),
            distribution_config=distribution,
            orientation_field=analysis.tangent_field,
            orientation_config=orientation,
            style_config=style,
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

    svg = render_to_svg(glyphs, width=analysis.width, height=analysis.height)
    svg_path.write_text(svg, encoding="utf-8")
    _write_json(json_path, [glyph.model_dump() for glyph in glyphs])

    zone_counts = Counter(glyph.zone for glyph in glyphs)
    layer_counts = Counter(glyph.layer for glyph in glyphs)
    role_counts = Counter(glyph.style_role for glyph in glyphs)
    orientation_counts = Counter(glyph.orientation_source for glyph in glyphs)
    strengths = [
        glyph.orientation_strength
        for glyph in glyphs
        if glyph.orientation_source == "tangent"
    ]

    report = validate_scene(glyphs, target_object.allowed_characters, svg)
    report.update(
        {
            "seed": target_object.seed,
            "word": target_object.word,
            "character_sequence": list(target_object.character_sequence),
            "layer_mode": "balanced",
            "distribution": asdict(distribution),
            "balanced_style": asdict(style),
            "zone_counts": {
                zone: zone_counts.get(zone, 0) for zone in ("edge", "mid", "core")
            },
            "layer_counts": {
                layer: layer_counts.get(layer, 0)
                for layer in ("outline", "fill", "texture")
            },
            "style_role_counts": {
                role: role_counts.get(role, 0) for role in STYLE_ROLE_ORDER
            },
            "layer_metrics": summarize_layer_metrics(glyphs),
            "balanced_role_metrics": summarize_balanced_metrics(
                glyphs,
                metric_cell_size=style.metric_cell_size,
            ),
            "orientation": {
                **asdict(orientation),
                "smoothing": args.orientation_smoothing,
            },
            "orientation_counts": {
                source: orientation_counts.get(source, 0)
                for source in ("tangent", "random")
            },
            "mean_orientation_strength": fmean(strengths) if strengths else 0.0,
        }
    )
    _write_json(report_path, report)

    if not report["is_valid"]:
        print(f"Validação reprovada. Consulte: {report_path}")
        return 1

    if not args.skip_png:
        try:
            export_to_png(svg, str(png_path))
        except Exception as error:
            print(f"Aviso: não foi possível gerar a prévia PNG: {error}")
            return 1

    print("Validação aprovada: SVG estrito e caracteres semânticos corretos.")
    print(
        "Camadas: "
        f"outline={layer_counts.get('outline', 0)}, "
        f"fill={layer_counts.get('fill', 0)}, "
        f"texture={layer_counts.get('texture', 0)}"
    )
    print(
        "Papéis balanceados: "
        f"outline_shadow={role_counts.get('outline_shadow', 0)}, "
        f"outline_detail={role_counts.get('outline_detail', 0)}, "
        f"fill_mass={role_counts.get('fill_mass', 0)}, "
        f"texture_accent={role_counts.get('texture_accent', 0)}"
    )
    print(f"Artefatos gerados em: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
