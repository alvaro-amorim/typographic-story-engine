from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from api_server.app import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Typographic Story Engine API"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/api-jobs"),
    )
    parser.add_argument("--reload", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("Erro: --port deve estar entre 1 e 65535")
        return 2

    app = create_app(output_root=args.output_dir)
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
