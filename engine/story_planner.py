from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from engine.animation_models import SceneAnimationSpec
from engine.asset_registry import AssetRegistry, AssetSpec, normalize_story_text
from engine.scene_models import SceneObjectSpec, SceneSpec, SceneTransform
from engine.story_models import (
    MovementDirection,
    StoryDecision,
    StoryPlanManifest,
    StoryPlanOutput,
)

_LEFT_PHRASES = (
    "walks left",
    "moves left",
    "flies left",
    "goes left",
    "to the left",
    "caminha para esquerda",
    "anda para esquerda",
    "voa para esquerda",
    "vai para esquerda",
    "para a esquerda",
)
_RIGHT_PHRASES = (
    "walks right",
    "moves right",
    "flies right",
    "goes right",
    "to the right",
    "caminha para direita",
    "anda para direita",
    "voa para direita",
    "vai para direita",
    "para a direita",
)
_MOVEMENT_PHRASES = (
    "walks",
    "walk",
    "moves",
    "move",
    "flies",
    "fly",
    "flying",
    "goes away",
    "walks away",
    "leaves",
    "caminha",
    "anda",
    "voa",
    "voam",
    "voando",
    "vai embora",
    "se afasta",
    "afasta",
)
_AWAY_PHRASES = ("walks away", "goes away", "leaves", "vai embora", "se afasta")


@dataclass(frozen=True)
class PlannedStoryBundle:
    manifest: StoryPlanManifest
    first_scene: SceneSpec
    second_scene: SceneSpec
    animation: SceneAnimationSpec


def _contains_phrase(normalized_story: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {normalized_story} "
    return any(f" {normalize_story_text(phrase)} " in padded for phrase in phrases)


def _subject_candidates(registry: AssetRegistry, normalized_story: str) -> list[AssetSpec]:
    tagged = [asset for asset in registry.assets if "subject" in asset.tags]
    matched = [asset for asset in tagged if asset.matches(normalized_story)]
    return sorted(
        matched,
        key=lambda asset: (
            -max((len(alias) for alias in asset.aliases), default=0),
            asset.id,
        ),
    )


def _movement_direction(normalized_story: str) -> MovementDirection:
    if _contains_phrase(normalized_story, _LEFT_PHRASES):
        return "left"
    if _contains_phrase(normalized_story, _RIGHT_PHRASES):
        return "right"
    if _contains_phrase(normalized_story, _MOVEMENT_PHRASES):
        return "right"
    return "pose"


def deterministic_story_decision(
    story: str,
    registry: AssetRegistry,
    *,
    movement_fraction: float = 0.28,
) -> StoryDecision:
    normalized_story = normalize_story_text(story)
    if not normalized_story:
        raise ValueError("story cannot be blank")
    if not 0.0 <= movement_fraction <= 1.0:
        raise ValueError("movement_fraction must be between zero and one")

    candidates = _subject_candidates(registry, normalized_story)
    if not candidates:
        aliases = sorted(
            {
                alias
                for asset in registry.assets
                if "subject" in asset.tags
                for alias in asset.aliases
            }
        )
        raise ValueError(
            "no supported subject was found in the story; available aliases: "
            + ", ".join(aliases)
        )

    subject = candidates[0]
    included = [
        asset
        for asset in registry.assets
        if asset.id == subject.id
        or asset.always_include
        or asset.matches(normalized_story)
    ]
    included.sort(key=lambda asset: (asset.z_index, asset.id))
    return StoryDecision(
        subject_asset_id=subject.id,
        included_asset_ids=[asset.id for asset in included],
        movement_direction=_movement_direction(normalized_story),
        movement_fraction=movement_fraction,
    )


def _story_id(story: str, explicit: str | None) -> str:
    if explicit is not None:
        normalized = explicit.strip()
        if not normalized or any(character.isspace() for character in normalized):
            raise ValueError("story id cannot be blank or contain whitespace")
        return normalized
    digest = hashlib.sha256(story.encode("utf-8")).hexdigest()[:10]
    return f"story_{digest}"


def _validated_decision_assets(
    registry: AssetRegistry,
    decision: StoryDecision,
) -> tuple[AssetSpec, list[AssetSpec]]:
    assets_by_id = registry.by_id()
    unknown = sorted(
        {
            asset_id
            for asset_id in [decision.subject_asset_id, *decision.included_asset_ids]
            if asset_id not in assets_by_id
        }
    )
    if unknown:
        raise ValueError("story decision references unknown assets: " + ", ".join(unknown))

    subject = assets_by_id[decision.subject_asset_id]
    if "subject" not in subject.tags:
        raise ValueError(
            f"story decision subject '{subject.id}' is not tagged as a subject"
        )

    included_ids = set(decision.included_asset_ids)
    included_ids.add(subject.id)
    included_ids.update(asset.id for asset in registry.assets if asset.always_include)
    included = [assets_by_id[asset_id] for asset_id in included_ids]
    included.sort(key=lambda asset: (asset.z_index, asset.id))
    return subject, included


def _scene_object(asset: AssetSpec, transform: SceneTransform) -> SceneObjectSpec:
    if not asset.glyphs_path.is_file():
        raise ValueError(
            f"glyph-state file was not found for asset '{asset.id}': {asset.glyphs_path}"
        )
    return SceneObjectSpec(
        id=asset.id,
        word=asset.word,
        glyphs_path=asset.glyphs_path.resolve(),
        transform=transform,
        z_index=asset.z_index,
        visible=asset.visible,
    )


def _end_subject_transform(
    start: SceneTransform,
    *,
    direction: MovementDirection,
    movement_distance: float,
    canvas_height: int,
    normalized_story: str,
) -> SceneTransform:
    if direction == "pose":
        return start.model_copy(update={"rotation": start.rotation - 3.0})

    sign = -1.0 if direction == "left" else 1.0
    away = _contains_phrase(normalized_story, _AWAY_PHRASES)
    scale_factor = 0.94 if away else 1.0
    return start.model_copy(
        update={
            "x": start.x + sign * movement_distance,
            "y": start.y + canvas_height * 0.012,
            "scale_x": start.scale_x * scale_factor,
            "scale_y": start.scale_y * scale_factor,
            "rotation": start.rotation + (-4.0 if direction == "right" else 4.0),
        }
    )


def plan_story_from_decision(
    story: str,
    registry: AssetRegistry,
    decision: StoryDecision,
    *,
    story_id: str | None = None,
    duration_seconds: float = 2.0,
    fps: int = 12,
    easing: str = "ease_in_out",
    registry_file: str = "",
    planner_provider: str = "deterministic",
    planner_model: str | None = None,
    planner_fallback_used: bool = False,
    planner_error: str | None = None,
) -> PlannedStoryBundle:
    normalized_story = normalize_story_text(story)
    if not normalized_story:
        raise ValueError("story cannot be blank")

    subject, included = _validated_decision_assets(registry, decision)
    movement_distance = (
        registry.width * decision.movement_fraction
        if decision.movement_direction != "pose"
        else 0.0
    )
    identifier = _story_id(story, story_id)

    first_objects = [
        _scene_object(asset, asset.transform.model_copy(deep=True)) for asset in included
    ]
    second_objects: list[SceneObjectSpec] = []
    for asset in included:
        transform = asset.transform.model_copy(deep=True)
        if asset.id == subject.id:
            transform = _end_subject_transform(
                transform,
                direction=decision.movement_direction,
                movement_distance=movement_distance,
                canvas_height=registry.height,
                normalized_story=normalized_story,
            )
        second_objects.append(_scene_object(asset, transform))

    first_name = f"{identifier}_scene_001.json"
    second_name = f"{identifier}_scene_002.json"
    animation_name = f"{identifier}_animation.json"
    first_scene = SceneSpec(
        id=f"{identifier}_scene_001",
        width=registry.width,
        height=registry.height,
        background=registry.background,
        objects=first_objects,
    )
    second_scene = SceneSpec(
        id=f"{identifier}_scene_002",
        width=registry.width,
        height=registry.height,
        background=registry.background,
        objects=second_objects,
    )
    animation = SceneAnimationSpec(
        id=f"{identifier}_transition_001",
        from_scene=Path(first_name),
        to_scene=Path(second_name),
        duration_seconds=duration_seconds,
        fps=fps,
        easing=easing,
    )
    manifest = StoryPlanManifest(
        id=identifier,
        story=story,
        normalized_story=normalized_story,
        template_id=f"two_scene_subject_{decision.movement_direction}",
        subject_asset_id=subject.id,
        included_asset_ids=[asset.id for asset in included],
        movement_direction=decision.movement_direction,
        movement_distance=movement_distance,
        scene_files=[first_name, second_name],
        animation_file=animation_name,
        registry_file=registry_file,
        planner_provider=planner_provider,
        planner_model=planner_model,
        planner_fallback_used=planner_fallback_used,
        planner_error=planner_error,
    )
    return PlannedStoryBundle(
        manifest=manifest,
        first_scene=first_scene,
        second_scene=second_scene,
        animation=animation,
    )


def plan_story(
    story: str,
    registry: AssetRegistry,
    *,
    story_id: str | None = None,
    duration_seconds: float = 2.0,
    fps: int = 12,
    easing: str = "ease_in_out",
    movement_fraction: float = 0.28,
    registry_file: str = "",
) -> PlannedStoryBundle:
    decision = deterministic_story_decision(
        story,
        registry,
        movement_fraction=movement_fraction,
    )
    return plan_story_from_decision(
        story,
        registry,
        decision,
        story_id=story_id,
        duration_seconds=duration_seconds,
        fps=fps,
        easing=easing,
        registry_file=registry_file,
    )


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def write_story_plan(
    bundle: PlannedStoryBundle,
    output_dir: str | Path,
) -> StoryPlanOutput:
    root = Path(output_dir).resolve() / bundle.manifest.id
    root.mkdir(parents=True, exist_ok=True)
    first_path = root / bundle.manifest.scene_files[0]
    second_path = root / bundle.manifest.scene_files[1]
    animation_path = root / bundle.manifest.animation_file
    manifest_path = root / f"{bundle.manifest.id}_plan.json"

    _write_json(first_path, bundle.first_scene.model_dump(mode="json"))
    _write_json(second_path, bundle.second_scene.model_dump(mode="json"))
    _write_json(animation_path, bundle.animation.model_dump(mode="json"))
    _write_json(manifest_path, bundle.manifest.model_dump(mode="json"))

    return StoryPlanOutput(
        root=root,
        manifest=manifest_path,
        first_scene=first_path,
        second_scene=second_path,
        animation=animation_path,
    )
