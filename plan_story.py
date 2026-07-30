from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from engine.asset_registry import load_asset_registry, resolve_registry_paths
from engine.planner_providers import (
    DeterministicPlannerProvider,
    OllamaPlannerProvider,
    plan_story_with_provider,
)
from engine.scene_animation import prepare_scene_animation, resolve_animation_paths
from engine.story_planner import write_story_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a short story into two persistent-object scenes"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--story", help="Short story text")
    source.add_argument("--story-file", type=Path, help="UTF-8 file containing the story")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--id", default=None, help="Optional deterministic story ID")
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument(
        "--easing",
        choices=("linear", "ease_in", "ease_out", "ease_in_out"),
        default="ease_in_out",
    )
    parser.add_argument("--movement-fraction", type=float, default=0.28)
    parser.add_argument(
        "--provider",
        choices=("deterministic", "ollama"),
        default="deterministic",
    )
    parser.add_argument(
        "--ollama-model",
        default=None,
        help="Required when --provider ollama is selected",
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
        help="Ollama base URL",
    )
    parser.add_argument("--ollama-timeout", type=float, default=60.0)
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail instead of falling back to the deterministic planner",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/story-plans"),
    )
    return parser


def _story_text(args: argparse.Namespace) -> str:
    if args.story is not None:
        return args.story
    if not args.story_file.is_file():
        raise ValueError(f"story file was not found: {args.story_file}")
    return args.story_file.read_text(encoding="utf-8")


def _provider(args: argparse.Namespace):
    if args.provider == "deterministic":
        return DeterministicPlannerProvider(
            movement_fraction=args.movement_fraction
        )
    if not args.ollama_model:
        raise ValueError("--ollama-model is required when --provider ollama is selected")
    return OllamaPlannerProvider(
        model=args.ollama_model,
        base_url=args.ollama_url,
        timeout_seconds=args.ollama_timeout,
        movement_fraction=args.movement_fraction,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.registry.is_file():
        print(f"Erro: o catálogo de assets '{args.registry}' não foi encontrado.")
        return 2

    try:
        story = _story_text(args)
        registry = resolve_registry_paths(
            load_asset_registry(args.registry),
            args.registry,
        )
        provider = _provider(args)
        bundle = plan_story_with_provider(
            story,
            registry,
            provider,
            story_id=args.id,
            duration_seconds=args.duration,
            fps=args.fps,
            easing=args.easing,
            registry_file=str(args.registry.resolve()),
            fallback_to_deterministic=not args.no_fallback,
            fallback_movement_fraction=args.movement_fraction,
        )
        output = write_story_plan(bundle, args.output_dir)
        animation = resolve_animation_paths(
            bundle.animation,
            output.animation,
        )
        prepare_scene_animation(animation)
    except (OSError, RuntimeError, ValueError, ValidationError) as error:
        print("Erro ao planejar a história:")
        print(error)
        return 2

    print(
        f"História planejada: template={bundle.manifest.template_id}, "
        f"subject={bundle.manifest.subject_asset_id}."
    )
    print(
        f"Planner: {bundle.manifest.planner_provider}"
        + (
            f" ({bundle.manifest.planner_model})"
            if bundle.manifest.planner_model
            else ""
        )
        + (" [fallback]" if bundle.manifest.planner_fallback_used else "")
    )
    if bundle.manifest.planner_error:
        print(f"Aviso do provider: {bundle.manifest.planner_error}")
    print("Assets: " + " -> ".join(bundle.manifest.included_asset_ids))
    print(f"Cena inicial: {output.first_scene}")
    print(f"Cena final: {output.second_scene}")
    print(f"Animação: {output.animation}")
    print(f"Plano: {output.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
