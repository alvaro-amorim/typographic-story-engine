from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import fmean
from typing import Any, Sequence

from pydantic import ValidationError

from engine.balanced_styling import (
    BalancedStyleConfig,
    distribute_balanced_glyphs,
    summarize_balanced_metrics,
)
from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    distribute_glyphs,
)
from engine.image_analysis import analyze_mask
from engine.layered_distribution import (
    LayerConfig,
    distribute_layered_glyphs,
    summarize_layer_metrics,
)
from engine.models import Glyph, SemanticObject
from engine.organic_styling import (
    OrganicStyleConfig,
    STYLE_ROLE_ORDER,
    distribute_organic_glyphs,
    summarize_organic_metrics,
)
from engine.png_exporter import export_to_png
from engine.semantic_validation import validate_scene
from engine.svg_renderer import render_to_svg

DEFAULT_PALETTE = ["#2C303A", "#4F5D75", "#BFC0C0", "#EAE2B7"]
RENDER_MODES = ("balanced", "organic", "layered", "legacy")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Typographic Story Engine - strict text-only SVG renderer"
    )
    parser.add_argument("--id", default="obj_01", help="Unique object ID")
    parser.add_argument("--word", required=True, help="Word used to build the object")
    parser.add_argument("--mask", type=Path, required=True, help="Path to a PNG mask")
    parser.add_argument("--count", type=int, default=12000, help="Number of glyphs")
    parser.add_argument("--font-min", type=float, default=8.0, help="Minimum font size")
    parser.add_argument("--font-max", type=float, default=28.0, help="Maximum font size")
    parser.add_argument("--rotation-min", type=float, default=-12.0)
    parser.add_argument("--rotation-max", type=float, default=12.0)
    parser.add_argument(
        "--palette",
        nargs="+",
        default=DEFAULT_PALETTE,
        metavar="HEX",
        help="One or more six-digit hexadecimal colors",
    )
    parser.add_argument("--seed", type=int, default=817392)
    parser.add_argument(
        "--layer-mode",
        choices=RENDER_MODES,
        default="balanced",
        help="Renderer strategy. The production default is balanced.",
    )

    # Shared layer controls. None lets each historical mode retain its own defaults.
    parser.add_argument("--outline-ratio", type=float, default=None)
    parser.add_argument("--fill-ratio", type=float, default=None)
    parser.add_argument("--texture-ratio", type=float, default=None)
    parser.add_argument("--outline-depth-max", type=float, default=None)
    parser.add_argument("--fill-depth-min", type=float, default=None)
    parser.add_argument("--texture-depth-min", type=float, default=None)
    parser.add_argument("--outline-shadow-fraction", type=float, default=None)
    parser.add_argument("--outline-detail-depth-max", type=float, default=None)
    parser.add_argument("--outline-shadow-depth-min", type=float, default=None)
    parser.add_argument("--organic-scale", type=float, default=None)
    parser.add_argument("--texture-opacity-min", type=float, default=None)
    parser.add_argument("--texture-opacity-max", type=float, default=None)

    # Balanced renderer controls.
    parser.add_argument("--outline-coherence", type=float, default=None)
    parser.add_argument("--fill-modulation-strength", type=float, default=None)
    parser.add_argument("--fill-opacity-min", type=float, default=None)
    parser.add_argument("--fill-opacity-max", type=float, default=None)
    parser.add_argument("--fill-dark-probability", type=float, default=None)
    parser.add_argument("--metric-cell-size", type=int, default=None)

    # Legacy zone distribution controls.
    parser.add_argument("--edge-threshold", type=float, default=0.18)
    parser.add_argument("--mid-threshold", type=float, default=0.55)
    parser.add_argument("--edge-ratio", type=float, default=0.45)
    parser.add_argument("--mid-ratio", type=float, default=0.35)
    parser.add_argument("--core-ratio", type=float, default=0.20)
    parser.add_argument("--cell-size", type=int, default=8)
    parser.add_argument("--edge-capacity", type=int, default=4)
    parser.add_argument("--mid-capacity", type=int, default=3)
    parser.add_argument("--core-capacity", type=int, default=2)

    # Orientation controls shared by every modern renderer.
    parser.add_argument(
        "--orientation-mode",
        choices=("tangent", "random"),
        default="tangent",
    )
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


def _override(value: Any, fallback: Any) -> Any:
    return fallback if value is None else value


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_configs(args: argparse.Namespace) -> tuple[
    SemanticObject,
    DistributionConfig,
    OrientationConfig,
    LayerConfig,
    OrganicStyleConfig,
    BalancedStyleConfig,
]:
    target = SemanticObject(
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
        edge_ratio=args.edge_ratio,
        mid_ratio=args.mid_ratio,
        core_ratio=args.core_ratio,
        cell_size=args.cell_size,
        edge_capacity=args.edge_capacity,
        mid_capacity=args.mid_capacity,
        core_capacity=args.core_capacity,
    )
    orientation = OrientationConfig(
        enabled=args.orientation_mode == "tangent",
        adaptive=True,
        edge_strength=args.edge_orientation_strength,
        mid_strength=args.mid_orientation_strength,
        core_strength=args.core_orientation_strength,
        jitter_degrees=args.orientation_jitter,
        min_confidence=args.orientation_min_confidence,
        confidence_power=args.orientation_confidence_power,
    )

    layered_defaults = LayerConfig()
    layered = LayerConfig(
        enabled=args.layer_mode == "layered",
        outline_ratio=_override(args.outline_ratio, layered_defaults.outline_ratio),
        fill_ratio=_override(args.fill_ratio, layered_defaults.fill_ratio),
        texture_ratio=_override(args.texture_ratio, layered_defaults.texture_ratio),
        outline_depth_max=_override(
            args.outline_depth_max, layered_defaults.outline_depth_max
        ),
        fill_depth_min=_override(args.fill_depth_min, layered_defaults.fill_depth_min),
        texture_depth_min=_override(
            args.texture_depth_min, layered_defaults.texture_depth_min
        ),
    )

    organic_defaults = OrganicStyleConfig()
    organic = OrganicStyleConfig(
        outline_ratio=_override(args.outline_ratio, organic_defaults.outline_ratio),
        fill_ratio=_override(args.fill_ratio, organic_defaults.fill_ratio),
        texture_ratio=_override(args.texture_ratio, organic_defaults.texture_ratio),
        outline_shadow_fraction=_override(
            args.outline_shadow_fraction, organic_defaults.outline_shadow_fraction
        ),
        outline_detail_depth_max=_override(
            args.outline_detail_depth_max, organic_defaults.outline_detail_depth_max
        ),
        outline_shadow_depth_min=_override(
            args.outline_shadow_depth_min, organic_defaults.outline_shadow_depth_min
        ),
        outline_depth_max=_override(
            args.outline_depth_max, organic_defaults.outline_depth_max
        ),
        fill_depth_min=_override(args.fill_depth_min, organic_defaults.fill_depth_min),
        texture_depth_min=_override(
            args.texture_depth_min, organic_defaults.texture_depth_min
        ),
        organic_scale=_override(args.organic_scale, organic_defaults.organic_scale),
        texture_opacity_min=_override(
            args.texture_opacity_min, organic_defaults.texture_opacity_min
        ),
        texture_opacity_max=_override(
            args.texture_opacity_max, organic_defaults.texture_opacity_max
        ),
    )

    balanced_defaults = BalancedStyleConfig()
    balanced = BalancedStyleConfig(
        outline_ratio=_override(args.outline_ratio, balanced_defaults.outline_ratio),
        fill_ratio=_override(args.fill_ratio, balanced_defaults.fill_ratio),
        texture_ratio=_override(args.texture_ratio, balanced_defaults.texture_ratio),
        outline_shadow_fraction=_override(
            args.outline_shadow_fraction, balanced_defaults.outline_shadow_fraction
        ),
        outline_detail_depth_max=_override(
            args.outline_detail_depth_max, balanced_defaults.outline_detail_depth_max
        ),
        outline_shadow_depth_min=_override(
            args.outline_shadow_depth_min, balanced_defaults.outline_shadow_depth_min
        ),
        outline_depth_max=_override(
            args.outline_depth_max, balanced_defaults.outline_depth_max
        ),
        fill_depth_min=_override(args.fill_depth_min, balanced_defaults.fill_depth_min),
        texture_depth_min=_override(
            args.texture_depth_min, balanced_defaults.texture_depth_min
        ),
        organic_scale=_override(args.organic_scale, balanced_defaults.organic_scale),
        outline_coherence=_override(
            args.outline_coherence, balanced_defaults.outline_coherence
        ),
        fill_modulation_strength=_override(
            args.fill_modulation_strength, balanced_defaults.fill_modulation_strength
        ),
        fill_opacity_min=_override(
            args.fill_opacity_min, balanced_defaults.fill_opacity_min
        ),
        fill_opacity_max=_override(
            args.fill_opacity_max, balanced_defaults.fill_opacity_max
        ),
        fill_dark_probability=_override(
            args.fill_dark_probability, balanced_defaults.fill_dark_probability
        ),
        texture_opacity_min=_override(
            args.texture_opacity_min, balanced_defaults.texture_opacity_min
        ),
        texture_opacity_max=_override(
            args.texture_opacity_max, balanced_defaults.texture_opacity_max
        ),
        metric_cell_size=_override(
            args.metric_cell_size, balanced_defaults.metric_cell_size
        ),
    )
    return target, distribution, orientation, layered, organic, balanced


def _render_glyphs(
    args: argparse.Namespace,
    target: SemanticObject,
    distribution: DistributionConfig,
    orientation: OrientationConfig,
    layered: LayerConfig,
    organic: OrganicStyleConfig,
    balanced: BalancedStyleConfig,
):
    analysis = analyze_mask(
        target.mask_path,
        orientation_smoothing=args.orientation_smoothing,
    )
    common = {
        "object_id": target.id,
        "valid_coords": analysis.valid_coordinates,
        "character_sequence": target.character_sequence,
        "glyph_count": target.glyph_count,
        "font_size_range": target.font_size_range,
        "palette": target.palette,
        "seed": target.seed,
        "rotation_range": (args.rotation_min, args.rotation_max),
        "distribution_config": distribution,
        "orientation_field": analysis.tangent_field if orientation.enabled else None,
        "orientation_config": orientation,
    }
    if args.layer_mode == "balanced":
        glyphs = distribute_balanced_glyphs(**common, style_config=balanced)
    elif args.layer_mode == "organic":
        glyphs = distribute_organic_glyphs(**common, style_config=organic)
    elif args.layer_mode == "layered":
        glyphs = distribute_layered_glyphs(**common, layer_config=layered)
    else:
        glyphs = distribute_glyphs(**common)
    return analysis, glyphs


def _renderer_metrics(
    mode: str,
    glyphs: Sequence[Glyph],
    balanced: BalancedStyleConfig,
) -> dict[str, object]:
    if mode == "balanced":
        return {
            "balanced_role_metrics": summarize_balanced_metrics(
                glyphs,
                metric_cell_size=balanced.metric_cell_size,
            )
        }
    if mode == "organic":
        return {"style_role_metrics": summarize_organic_metrics(glyphs)}
    return {}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.mask.is_file():
        print(f"Erro: a máscara '{args.mask}' não foi encontrada ou não é um arquivo.")
        return 2

    try:
        target, distribution, orientation, layered, organic, balanced = _build_configs(args)
        analysis, glyphs = _render_glyphs(
            args,
            target,
            distribution,
            orientation,
            layered,
            organic,
            balanced,
        )
    except (ValidationError, OSError, ValueError) as error:
        print("Erro durante a configuração ou geração:")
        print(error)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = target.id
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
    tangent_confidences = [
        glyph.orientation_confidence
        for glyph in glyphs
        if glyph.orientation_source == "tangent"
    ]
    tangent_strengths = [
        glyph.orientation_strength
        for glyph in glyphs
        if glyph.orientation_source == "tangent"
    ]
    strength_by_zone = {
        zone: [glyph.orientation_strength for glyph in glyphs if glyph.zone == zone]
        for zone in ("edge", "mid", "core")
    }

    active_config: object = {
        "balanced": balanced,
        "organic": organic,
        "layered": layered,
        "legacy": distribution,
    }[args.layer_mode]
    report = validate_scene(glyphs, target.allowed_characters, svg)
    report.update(
        {
            "renderer_version": "0.1.0",
            "layer_mode": args.layer_mode,
            "seed": target.seed,
            "word": target.word,
            "character_sequence": list(target.character_sequence),
            "distribution": asdict(distribution),
            "renderer_config": asdict(active_config),
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
            "orientation": {
                **asdict(orientation),
                "mode": args.orientation_mode,
                "smoothing": args.orientation_smoothing,
                "zone_jitters": orientation.zone_jitters,
                "zone_min_confidences": orientation.zone_min_confidences,
                "zone_depth_falloffs": orientation.zone_depth_falloffs,
            },
            "orientation_counts": {
                source: orientation_counts.get(source, 0)
                for source in ("tangent", "random")
            },
            "mean_tangent_confidence": (
                fmean(tangent_confidences) if tangent_confidences else 0.0
            ),
            "mean_orientation_strength": (
                fmean(tangent_strengths) if tangent_strengths else 0.0
            ),
            "mean_orientation_strength_by_zone": {
                zone: fmean(values) if values else 0.0
                for zone, values in strength_by_zone.items()
            },
            **_renderer_metrics(args.layer_mode, glyphs, balanced),
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

    print(
        f"Validação aprovada: renderer={args.layer_mode}, "
        "SVG estrito e caracteres semânticos corretos."
    )
    print(
        "Camadas: "
        f"outline={layer_counts.get('outline', 0)}, "
        f"fill={layer_counts.get('fill', 0)}, "
        f"texture={layer_counts.get('texture', 0)}"
    )
    if args.layer_mode in {"balanced", "organic"}:
        print(
            "Papéis: "
            f"outline_shadow={role_counts.get('outline_shadow', 0)}, "
            f"outline_detail={role_counts.get('outline_detail', 0)}, "
            f"fill_mass={role_counts.get('fill_mass', 0)}, "
            f"texture_accent={role_counts.get('texture_accent', 0)}"
        )
    print(f"Artefatos gerados em: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
