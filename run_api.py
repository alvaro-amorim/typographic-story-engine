from __future__ import annotations

import argparse
import os
import threading
import webbrowser
from pathlib import Path
from typing import Sequence

import uvicorn

from api_server.app import create_app
from api_server.studio_assets import DEFAULT_STUDIO_ROOT, ensure_default_registry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the local Typographic Story Engine API and prompt studio"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/api-jobs"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=None,
        help="Use an existing Asset Registry instead of the automatic studio registry.",
    )
    parser.add_argument(
        "--studio-assets-dir",
        type=Path,
        default=DEFAULT_STUDIO_ROOT,
        help="Cache directory used to build the default studio registry.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        action="store_true",
        help="Start without building a default registry. Advanced /v1/jobs remains available.",
    )
    parser.add_argument("--reload", action="store_true")
    parser.add_argument("--open-browser", action="store_true")
    return parser


def _open_browser_later(url: str) -> None:
    timer = threading.Timer(1.1, lambda: webbrowser.open(url))
    timer.daemon = True
    timer.start()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("Erro: --port deve estar entre 1 e 65535")
        return 2

    try:
        if args.registry is not None:
            registry = args.registry.resolve()
            if not registry.is_file():
                print(f"Erro: registry não encontrado: {registry}")
                return 2
        elif args.skip_bootstrap:
            registry = None
        else:
            print("Preparando catálogo padrão do Studio...")
            registry = ensure_default_registry(args.studio_assets_dir)
            print(f"Registry pronto: {registry}")
    except (OSError, RuntimeError, ValueError) as error:
        print("Erro ao preparar o Studio:")
        print(error)
        return 2

    studio_url = f"http://{args.host}:{args.port}/studio"
    docs_url = f"http://{args.host}:{args.port}/docs"
    print(f"Studio: {studio_url}")
    print(f"OpenAPI: {docs_url}")
    if args.open_browser:
        _open_browser_later(studio_url)

    if args.reload:
        os.environ["TSE_API_OUTPUT_ROOT"] = str(args.output_dir.resolve())
        if registry is not None:
            os.environ["TSE_DEFAULT_REGISTRY_PATH"] = str(registry)
        else:
            os.environ.pop("TSE_DEFAULT_REGISTRY_PATH", None)
        uvicorn.run(
            "api_server.app:app",
            host=args.host,
            port=args.port,
            reload=True,
        )
    else:
        app = create_app(
            output_root=args.output_dir,
            default_registry_path=registry,
        )
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
