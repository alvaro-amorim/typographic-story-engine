from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.glyph_distribution import distribute_glyphs
from engine.image_analysis import get_valid_coordinates
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
        "--rotation-min", type=float, default=-12.0, help="Minimum glyph rotation"
    )
    parser.add_argument(
        "--rotation-max", type=float, default=12.0, help="Maximum glyph rotation"
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
    except ValidationError as error:
        print("Erro de configuração:")
        print(error)
        return 2

    print(
        f"Iniciando Typographic Story Engine: renderizando "
        f"'{target_object.word}' com seed {target_object.seed}..."
    )

    valid_pixels, image_width, image_height = get_valid_coordinates(
        target_object.mask_path
    )
    if not valid_pixels:
        print("Erro: a máscara não contém pixels escuros válidos para renderização.")
        return 2

    scene_glyphs = distribute_glyphs(
        object_id=target_object.id,
        valid_coords=valid_pixels,
        character_sequence=target_object.character_sequence,
        glyph_count=target_object.glyph_count,
        font_size_range=target_object.font_size_range,
        palette=target_object.palette,
        seed=target_object.seed,
        rotation_range=(args.rotation_min, args.rotation_max),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = target_object.id
    svg_path = args.output_dir / f"{base_name}_scene.svg"
    json_path = args.output_dir / f"{base_name}_scene.json"
    report_path = args.output_dir / f"{base_name}_validation.json"
    png_path = args.output_dir / f"{base_name}_preview.png"

    svg_output = render_to_svg(scene_glyphs, width=image_width, height=image_height)
    svg_path.write_text(svg_output, encoding="utf-8")
    _write_json(json_path, [glyph.model_dump() for glyph in scene_glyphs])

    report = validate_scene(
        scene_glyphs,
        target_object.allowed_characters,
        svg_output,
    )
    report["seed"] = target_object.seed
    report["word"] = target_object.word
    report["character_sequence"] = list(target_object.character_sequence)
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
    print(f"Artefatos gerados em: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
