from __future__ import annotations

from pathlib import Path

from engine.asset_registry import load_asset_registry


def registry_asset_summaries(registry_path: str | Path | None) -> list[dict[str, object]]:
    if registry_path is None:
        return []
    path = Path(registry_path)
    if not path.is_file():
        return []
    try:
        registry = load_asset_registry(path)
    except (OSError, ValueError):
        return []

    summaries = [
        {
            "id": asset.id,
            "word": asset.word,
            "aliases": asset.aliases,
            "tags": sorted(asset.tags),
            "kind": "subject" if "subject" in asset.tags else "environment",
            "always_include": asset.always_include,
            "facing": asset.facing,
        }
        for asset in registry.assets
    ]
    return sorted(
        summaries,
        key=lambda item: (
            0 if item["kind"] == "subject" else 1,
            str(item["word"]),
            str(item["id"]),
        ),
    )
