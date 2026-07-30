from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import ValidationError

from engine.asset_registry import AssetRegistry
from engine.story_models import StoryDecision
from engine.story_planner import (
    PlannedStoryBundle,
    deterministic_story_decision,
    plan_story_from_decision,
)


class PlannerProviderError(RuntimeError):
    """Raised when a provider cannot return a valid StoryDecision."""


class StoryPlannerProvider(Protocol):
    name: str
    model: str | None

    def decide(self, story: str, registry: AssetRegistry) -> StoryDecision: ...


@dataclass(frozen=True)
class DeterministicPlannerProvider:
    movement_fraction: float = 0.28
    name: str = "deterministic"
    model: str | None = None

    def decide(self, story: str, registry: AssetRegistry) -> StoryDecision:
        return deterministic_story_decision(
            story,
            registry,
            movement_fraction=self.movement_fraction,
        )


@dataclass(frozen=True)
class OllamaPlannerProvider:
    model: str
    base_url: str = "http://localhost:11434"
    timeout_seconds: float = 60.0
    movement_fraction: float = 0.28
    name: str = "ollama"

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ValueError("Ollama model cannot be blank")
        if self.timeout_seconds <= 0.0:
            raise ValueError("Ollama timeout must be greater than zero")
        if not 0.0 <= self.movement_fraction <= 1.0:
            raise ValueError("movement_fraction must be between zero and one")
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Ollama base URL must be an absolute HTTP(S) URL")

    @property
    def endpoint(self) -> str:
        return self.base_url.rstrip("/") + "/api/chat"

    def _asset_context(self, registry: AssetRegistry) -> list[dict[str, object]]:
        return [
            {
                "id": asset.id,
                "word": asset.word,
                "aliases": asset.aliases,
                "tags": sorted(asset.tags),
                "always_include": asset.always_include,
                "z_index": asset.z_index,
            }
            for asset in sorted(registry.assets, key=lambda item: (item.z_index, item.id))
        ]

    def _prompt(self, story: str, registry: AssetRegistry) -> str:
        context = {
            "story": story,
            "canvas": {"width": registry.width, "height": registry.height},
            "assets": self._asset_context(registry),
            "rules": [
                "subject_asset_id must reference an asset tagged subject",
                "included_asset_ids may only contain IDs listed in assets",
                "include assets explicitly relevant to the story",
                "movement_direction must be left, right, or pose",
                "use pose when the subject does not change position",
                f"movement_fraction should usually be {self.movement_fraction}",
                "do not invent assets, words, IDs, or scene geometry",
            ],
        }
        return (
            "Select a semantic story-planning decision from the supplied local asset registry. "
            "Return only data matching the provided JSON schema.\n\n"
            + json.dumps(context, indent=2, ensure_ascii=False)
        )

    def _request_payload(self, story: str, registry: AssetRegistry) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a scene planner. You select existing asset IDs only. "
                        "Never generate SVG, masks, code, or new asset names."
                    ),
                },
                {
                    "role": "user",
                    "content": self._prompt(story, registry),
                },
            ],
            "stream": False,
            "format": StoryDecision.model_json_schema(),
            "options": {"temperature": 0},
        }

    def decide(self, story: str, registry: AssetRegistry) -> StoryDecision:
        payload = json.dumps(
            self._request_payload(story, registry),
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            details = error.read().decode("utf-8", errors="replace")
            raise PlannerProviderError(
                f"Ollama HTTP {error.code}: {details or error.reason}"
            ) from error
        except (URLError, TimeoutError, OSError) as error:
            raise PlannerProviderError(f"Ollama connection failed: {error}") from error

        try:
            envelope = json.loads(body)
            content = envelope["message"]["content"]
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise PlannerProviderError(
                "Ollama returned an invalid chat response envelope"
            ) from error

        try:
            return StoryDecision.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as error:
            raise PlannerProviderError(
                f"Ollama returned an invalid StoryDecision: {error}"
            ) from error


def plan_story_with_provider(
    story: str,
    registry: AssetRegistry,
    provider: StoryPlannerProvider,
    *,
    story_id: str | None = None,
    duration_seconds: float = 2.0,
    fps: int = 12,
    easing: str = "ease_in_out",
    registry_file: str = "",
    fallback_to_deterministic: bool = True,
    fallback_movement_fraction: float = 0.28,
) -> PlannedStoryBundle:
    try:
        decision = provider.decide(story, registry)
        return plan_story_from_decision(
            story,
            registry,
            decision,
            story_id=story_id,
            duration_seconds=duration_seconds,
            fps=fps,
            easing=easing,
            registry_file=registry_file,
            planner_provider=provider.name,
            planner_model=provider.model,
        )
    except (PlannerProviderError, ValidationError, ValueError) as error:
        if provider.name == "deterministic" or not fallback_to_deterministic:
            raise

        fallback = DeterministicPlannerProvider(
            movement_fraction=fallback_movement_fraction
        )
        decision = fallback.decide(story, registry)
        return plan_story_from_decision(
            story,
            registry,
            decision,
            story_id=story_id,
            duration_seconds=duration_seconds,
            fps=fps,
            easing=easing,
            registry_file=registry_file,
            planner_provider=fallback.name,
            planner_model=None,
            planner_fallback_used=True,
            planner_error=f"{provider.name}: {error}",
        )
