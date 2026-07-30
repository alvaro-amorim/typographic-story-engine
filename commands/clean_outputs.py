from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS = REPOSITORY_ROOT / "outputs"


def clean_outputs(output_dir: str | Path = DEFAULT_OUTPUTS) -> list[Path]:
    root = Path(output_dir).resolve()
    repository = REPOSITORY_ROOT.resolve()
    if root == repository or not root.is_relative_to(repository):
        raise ValueError("refusing to clean a directory outside the repository")
    if root.name != "outputs" and not root.is_relative_to(DEFAULT_OUTPUTS.resolve()):
        raise ValueError("cleanup target must be outputs/ or one of its subdirectories")

    root.mkdir(parents=True, exist_ok=True)
    removed: list[Path] = []
    for child in root.iterdir():
        if child.name == ".gitkeep":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
        removed.append(child)

    if root == DEFAULT_OUTPUTS.resolve():
        (root / ".gitkeep").touch(exist_ok=True)
    return removed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Delete generated artifacts while preserving the outputs directory"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUTS,
        help="Directory to clean. It must remain inside this repository's outputs/ tree.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        removed = clean_outputs(args.output_dir)
    except (OSError, ValueError) as error:
        print("Erro ao limpar outputs:")
        print(error)
        return 2

    print(f"Outputs limpos: {len(removed)} item(ns) removido(s).")
    print(f"Diretório pronto: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
