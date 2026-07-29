from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.png_exporter import export_to_png
from engine.scene_composer import (
    build_scene_state,
    load_scene_objects,
    load_scene_spec,
    render_scene_svg,
    resolve_scene_paths,
    validate_composed_scene,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compose multiple semantic glyph objects into a strict SVG scene"
    )
    parser.add_argument("--scene", required=True, type=Path, help="Path to a scene JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/scenes"),
        help="Directory used for generated scene artifacts",
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
    if not args.scene.is_file():
        print(f"Erro: o arquivo de cena '{args.scene}' não foi encontrado.")
        return 2

    try:
        scene = resolve_scene_paths(load_scene_spec(args.scene), args.scene)
        objects = load_scene_objects(scene)
        svg_output = render_scene_svg(scene, objects)
        state = build_scene_state(scene, objects)
        report = validate_composed_scene(scene, objects, svg_output)
    except (OSError, ValueError, ValidationError) as error:
        print("Erro ao compor a cena:")
        print(error)
        return 2

    output_dir = args.output_dir / scene.id
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / f"{scene.id}_scene.svg"
    state_path = output_dir / f"{scene.id}_scene.json"
    report_path = output_dir / f"{scene.id}_validation.json"
    png_path = output_dir / f"{scene.id}_preview.png"

    svg_path.write_text(svg_output, encoding="utf-8")
    _write_json(state_path, state.model_dump(mode="json"))
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

    print("Cena validada: semântica por objeto e SVG estrito preservados.")
    print(
        f"Objetos: {report['visible_object_count']} visíveis / "
        f"{report['total_object_count']} totais"
    )
    print(f"Glyphs totais: {report['total_glyph_count']}")
    print("Ordem de pintura: " + " -> ".join(report["object_order"]))
    print(f"Artefatos gerados em: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
