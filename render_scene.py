from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.png_exporter import export_to_png
from engine.scene_composer import (
    render_scene,
    render_scene_to_svg,
    scene_manifest,
    validate_rendered_scene,
)
from engine.scene_models import SceneDefinition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Typographic Story Engine - multi-object scene composer"
    )
    parser.add_argument("--scene", type=Path, required=True, help="Scene JSON file")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/scene"))
    parser.add_argument("--orientation-smoothing", type=float, default=2.0)
    parser.add_argument("--skip-png", action="store_true")
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.scene.is_file():
        print(f"Erro: o arquivo de cena '{args.scene}' não foi encontrado.")
        return 2

    try:
        definition = SceneDefinition.model_validate_json(
            args.scene.read_text(encoding="utf-8")
        )
        rendered = render_scene(
            definition,
            base_dir=args.scene.parent.resolve(),
            orientation_smoothing=args.orientation_smoothing,
        )
        svg = render_scene_to_svg(rendered)
        validation = validate_rendered_scene(rendered, svg)
    except (OSError, ValueError, ValidationError) as error:
        print("Erro ao compor a cena:")
        print(error)
        return 2

    args.output_dir.mkdir(parents=True, exist_ok=True)
    base_name = definition.id
    svg_path = args.output_dir / f"{base_name}_scene.svg"
    manifest_path = args.output_dir / f"{base_name}_scene.json"
    report_path = args.output_dir / f"{base_name}_validation.json"
    png_path = args.output_dir / f"{base_name}_preview.png"

    svg_path.write_text(svg, encoding="utf-8")
    _write_json(manifest_path, scene_manifest(rendered))
    _write_json(report_path, validation)

    if not validation["is_valid"]:
        print(f"Validação reprovada. Consulte: {report_path}")
        return 1

    if not args.skip_png:
        try:
            export_to_png(svg, str(png_path))
        except Exception as error:
            print(f"Aviso: não foi possível gerar a prévia PNG: {error}")
            return 1

    print(
        f"Cena '{definition.id}' aprovada: {validation['object_count']} objetos, "
        f"{validation['total_glyphs_rendered']} glyphs."
    )
    print("Ordem de pintura: " + " -> ".join(validation["object_order"]))
    print(f"Artefatos gerados em: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
