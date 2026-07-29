from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.animation_models import AnimationManifest
from engine.png_exporter import export_to_png
from engine.scene_animation import (
    frame_count,
    iter_animation_frames,
    load_animation_spec,
    prepare_scene_animation,
    resolve_animation_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interpolate two persistent-object scene graphs into SVG/PNG frames"
    )
    parser.add_argument(
        "--animation",
        required=True,
        type=Path,
        help="Path to an animation JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/animations"),
    )
    parser.add_argument("--skip-png", action="store_true")
    return parser


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.animation.is_file():
        print(f"Erro: o arquivo de animação '{args.animation}' não foi encontrado.")
        return 2

    try:
        spec = resolve_animation_paths(
            load_animation_spec(args.animation),
            args.animation,
        )
        prepared = prepare_scene_animation(spec)
    except (OSError, ValueError, ValidationError) as error:
        print("Erro ao preparar a animação:")
        print(error)
        return 2

    root = args.output_dir / spec.id
    svg_dir = root / "frames" / "svg"
    png_dir = root / "frames" / "png"
    svg_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_png:
        png_dir.mkdir(parents=True, exist_ok=True)

    total = frame_count(spec)
    padding = max(4, len(str(total - 1)))
    states = []
    invalid_frames: list[int] = []

    try:
        for frame in iter_animation_frames(prepared):
            name = f"frame_{frame.state.index:0{padding}d}"
            svg_path = svg_dir / f"{name}.svg"
            svg_path.write_text(frame.svg, encoding="utf-8")
            if not frame.validation["is_valid"]:
                invalid_frames.append(frame.state.index)
            if not args.skip_png:
                export_to_png(frame.svg, str(png_dir / f"{name}.png"))
            states.append(frame.state)
    except Exception as error:
        print(f"Erro durante a geração dos frames: {error}")
        return 1

    manifest = AnimationManifest(
        id=spec.id,
        duration_seconds=spec.duration_seconds,
        fps=spec.fps,
        easing=spec.easing,
        frame_count=len(states),
        from_scene=str(prepared.from_scene_path),
        to_scene=str(prepared.to_scene_path),
        object_ids=list(prepared.object_ids),
        frames=states,
    )
    report = {
        "is_valid": not invalid_frames and len(states) == total,
        "animation_id": spec.id,
        "expected_frame_count": total,
        "generated_frame_count": len(states),
        "invalid_frames": invalid_frames,
        "object_ids": list(prepared.object_ids),
        "glyphs_reused_per_frame": sum(
            len(item.glyphs) for item in prepared.source_objects
        ),
        "png_exported": not args.skip_png,
    }
    root.mkdir(parents=True, exist_ok=True)
    _write_json(root / f"{spec.id}_manifest.json", manifest.model_dump(mode="json"))
    _write_json(root / f"{spec.id}_validation.json", report)

    if not report["is_valid"]:
        print(f"Validação reprovada. Consulte: {root}")
        return 1

    print(
        f"Animação '{spec.id}' aprovada: {len(states)} frames, "
        f"{spec.duration_seconds:.2f}s a {spec.fps} fps."
    )
    print(
        f"Glyphs reutilizados por frame: {report['glyphs_reused_per_frame']}"
    )
    print(f"Artefatos gerados em: {root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
