from __future__ import annotations

import argparse
import importlib
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from api_server.ollama_service import OllamaServiceError, discover_ollama
from api_server.studio_assets import DEFAULT_STUDIO_ROOT, ensure_default_registry, registry_is_ready
from engine.silhouette_library import load_silhouette_catalog

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check whether the local Typographic Story Studio environment is ready"
    )
    parser.add_argument(
        "--ollama-url",
        default="http://localhost:11434",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=float,
        default=2.0,
        help="Timeout used for Ollama version and model discovery.",
    )
    parser.add_argument(
        "--prepare-assets",
        action="store_true",
        help="Build the default studio registry if it is not ready.",
    )
    return parser


def _status(label: str, ok: bool, detail: str) -> None:
    mark = "OK" if ok else "ERRO"
    print(f"[{mark}] {label}: {detail}")


def _check_imports() -> tuple[bool, str]:
    modules = ["fastapi", "uvicorn", "fitz", "PIL", "numpy", "scipy", "pydantic"]
    missing: list[str] = []
    for name in modules:
        try:
            importlib.import_module(name)
        except ImportError:
            missing.append(name)
    if missing:
        return False, "faltando " + ", ".join(missing)
    return True, "dependências Python disponíveis"


def _check_catalog() -> tuple[bool, str]:
    path = REPOSITORY_ROOT / "assets" / "catalog.json"
    try:
        catalog = load_silhouette_catalog(path)
    except (OSError, ValueError) as error:
        return False, str(error)
    return True, f"{len(catalog.assets)} assets validados"


def _check_ollama(base_url: str, timeout_seconds: float) -> tuple[bool, str]:
    try:
        status = discover_ollama(base_url, timeout_seconds=timeout_seconds)
    except (OllamaServiceError, ValueError) as error:
        return False, f"indisponível ({error})"
    names = [str(item["name"]) for item in status["models"]]
    model_detail = ", ".join(names) if names else "nenhum modelo instalado"
    return True, (
        f"versão {status['version']}; {status['latency_ms']} ms; "
        f"modelos: {model_detail}"
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    failures = 0

    python_ok = sys.version_info >= (3, 12)
    _status("Python", python_ok, sys.version.split()[0])
    failures += int(not python_ok)

    imports_ok, imports_detail = _check_imports()
    _status("Dependências", imports_ok, imports_detail)
    failures += int(not imports_ok)

    catalog_ok, catalog_detail = _check_catalog()
    _status("Catálogo", catalog_ok, catalog_detail)
    failures += int(not catalog_ok)

    ffmpeg = shutil.which("ffmpeg")
    _status("FFmpeg", ffmpeg is not None, ffmpeg or "não encontrado no PATH")
    failures += int(ffmpeg is None)

    registry_ready = registry_is_ready(DEFAULT_STUDIO_ROOT)
    if args.prepare_assets and not registry_ready:
        try:
            registry = ensure_default_registry(DEFAULT_STUDIO_ROOT)
            registry_ready = True
            registry_detail = str(registry)
        except (OSError, RuntimeError, ValueError) as error:
            registry_detail = str(error)
    else:
        registry_detail = (
            str(DEFAULT_STUDIO_ROOT / "asset_registry.json")
            if registry_ready
            else "será criado automaticamente ao iniciar o Studio"
        )
    _status("Registry do Studio", registry_ready, registry_detail)
    if args.prepare_assets:
        failures += int(not registry_ready)

    ollama_ok, ollama_detail = _check_ollama(args.ollama_url, args.ollama_timeout)
    _status("Ollama (opcional)", ollama_ok, ollama_detail)

    if failures:
        print(f"\nAmbiente com {failures} requisito(s) obrigatório(s) pendente(s).")
        return 1
    print("\nAmbiente pronto para gerar vídeos pelo Studio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
