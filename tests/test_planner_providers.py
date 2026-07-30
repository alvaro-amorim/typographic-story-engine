from __future__ import annotations

import json
from pathlib import Path

import pytest

import engine.planner_providers as providers
from engine.asset_registry import load_asset_registry, resolve_registry_paths
from engine.planner_providers import (
    OllamaPlannerProvider,
    PlannerProviderError,
    plan_story_with_provider,
)
from engine.story_models import StoryDecision


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self._body


def _write_glyphs(path: Path, word: str) -> None:
    payload = [
        {
            "id": f"glyph_{index}",
            "object_id": "source",
            "character": character,
            "x": 10 + index * 4,
            "y": 20,
            "font_size": 10,
            "opacity": 0.8,
            "color": "#172033",
        }
        for index, character in enumerate(word)
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(tmp_path: Path):
    _write_glyphs(tmp_path / "cat.json", "CAT")
    _write_glyphs(tmp_path / "moon.json", "MOON")
    _write_glyphs(tmp_path / "ground.json", "GROUND")
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "width": 1000,
                "height": 600,
                "background": "#F5F1E8",
                "assets": [
                    {
                        "id": "moon_01",
                        "word": "MOON",
                        "glyphs_path": "moon.json",
                        "aliases": ["moon", "lua"],
                        "tags": ["celestial"],
                        "z_index": 1,
                    },
                    {
                        "id": "ground_01",
                        "word": "GROUND",
                        "glyphs_path": "ground.json",
                        "aliases": ["ground", "chão"],
                        "tags": ["environment"],
                        "always_include": True,
                        "z_index": 2,
                    },
                    {
                        "id": "cat_01",
                        "word": "CAT",
                        "glyphs_path": "cat.json",
                        "aliases": ["cat", "gato"],
                        "tags": ["subject"],
                        "z_index": 3,
                        "transform": {"x": 200, "y": 250},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return resolve_registry_paths(load_asset_registry(path), path)


def test_ollama_provider_sends_json_schema_and_temperature_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry(tmp_path)
    captured: dict[str, object] = {}
    content = StoryDecision(
        subject_asset_id="cat_01",
        included_asset_ids=["cat_01", "moon_01"],
        movement_direction="right",
        movement_fraction=0.25,
    ).model_dump_json()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse({"message": {"content": content}})

    monkeypatch.setattr(providers, "urlopen", fake_urlopen)
    provider = OllamaPlannerProvider(
        model="qwen3:4b",
        base_url="http://localhost:11434",
        timeout_seconds=12,
    )
    decision = provider.decide("A cat walks away from the moon.", registry)
    request = captured["request"]
    payload = json.loads(request.data.decode("utf-8"))

    assert decision.subject_asset_id == "cat_01"
    assert request.full_url == "http://localhost:11434/api/chat"
    assert captured["timeout"] == 12
    assert payload["model"] == "qwen3:4b"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["format"]["type"] == "object"
    assert "subject_asset_id" in payload["format"]["properties"]
    assert "cat_01" in payload["messages"][1]["content"]


def test_ollama_invalid_response_raises_provider_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry(tmp_path)
    monkeypatch.setattr(
        providers,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse({"unexpected": True}),
    )
    provider = OllamaPlannerProvider(model="qwen3:4b")

    with pytest.raises(PlannerProviderError, match="invalid chat response"):
        provider.decide("A cat watches the moon.", registry)


def test_invalid_ollama_asset_falls_back_to_deterministic(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    class InvalidProvider:
        name = "ollama"
        model = "fake"

        def decide(self, story, registry):
            return StoryDecision(
                subject_asset_id="invented_dragon",
                included_asset_ids=["invented_castle"],
                movement_direction="right",
            )

    bundle = plan_story_with_provider(
        "A cat walks away from the moon.",
        registry,
        InvalidProvider(),
        story_id="fallback_story",
    )

    assert bundle.manifest.planner_provider == "deterministic"
    assert bundle.manifest.planner_fallback_used is True
    assert "unknown assets" in bundle.manifest.planner_error
    assert bundle.manifest.subject_asset_id == "cat_01"


def test_invalid_provider_does_not_fallback_when_disabled(tmp_path: Path) -> None:
    registry = _registry(tmp_path)

    class InvalidProvider:
        name = "ollama"
        model = "fake"

        def decide(self, story, registry):
            raise PlannerProviderError("model unavailable")

    with pytest.raises(PlannerProviderError, match="model unavailable"):
        plan_story_with_provider(
            "A cat watches the moon.",
            registry,
            InvalidProvider(),
            fallback_to_deterministic=False,
        )


def test_ollama_connection_failure_can_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = _registry(tmp_path)

    def fail(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(providers, "urlopen", fail)
    provider = OllamaPlannerProvider(model="qwen3:4b")
    bundle = plan_story_with_provider(
        "O gato olha para a lua e caminha para a esquerda.",
        registry,
        provider,
        story_id="offline_fallback",
    )

    assert bundle.manifest.planner_provider == "deterministic"
    assert bundle.manifest.planner_fallback_used is True
    assert bundle.manifest.movement_direction == "left"
    assert "connection failed" in bundle.manifest.planner_error
