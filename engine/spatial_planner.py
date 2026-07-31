from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, Field

from engine.asset_registry import AssetSpec, normalize_story_text
from engine.scene_models import SceneTransform

SpatialRelationName = Literal["above", "below", "near", "left_of", "right_of"]

_RELATION_PHRASES: dict[SpatialRelationName, tuple[str, ...]] = {
    "above": ("above", "over", "acima de", "por cima de"),
    "below": ("below", "under", "beneath", "abaixo de", "sob", "debaixo de"),
    "near": ("near", "beside", "next to", "perto de", "ao lado de"),
    "left_of": ("to the left of", "left of", "a esquerda de", "para a esquerda de"),
    "right_of": ("to the right of", "right of", "a direita de", "para a direita de"),
}


class SpatialRelation(BaseModel):
    subject_asset_id: str = Field(min_length=1)
    relation: SpatialRelationName
    reference_asset_id: str = Field(min_length=1)


@dataclass(frozen=True)
class LocalBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    @property
    def center_x(self) -> float:
        return (self.min_x + self.max_x) / 2.0

    @property
    def center_y(self) -> float:
        return (self.min_y + self.max_y) / 2.0


@dataclass(frozen=True)
class CanvasBounds:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2.0

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass(frozen=True)
class _AliasOccurrence:
    start: int
    end: int
    asset_id: str
    length: int


@dataclass(frozen=True)
class _RelationOccurrence:
    start: int
    end: int
    relation: SpatialRelationName
    length: int


def _token_sequences(values: Sequence[str]) -> list[tuple[str, ...]]:
    sequences: list[tuple[str, ...]] = []
    for value in values:
        normalized = normalize_story_text(value)
        tokens = tuple(normalized.split())
        if tokens and tokens not in sequences:
            sequences.append(tokens)
    return sequences


def _sequence_occurrences(tokens: list[str], sequence: tuple[str, ...]) -> list[tuple[int, int]]:
    length = len(sequence)
    return [
        (index, index + length)
        for index in range(0, len(tokens) - length + 1)
        if tuple(tokens[index : index + length]) == sequence
    ]


def parse_spatial_relations(
    story: str,
    assets: Sequence[AssetSpec],
) -> list[SpatialRelation]:
    """Extract explicit binary spatial relations from Portuguese or English text."""
    tokens = normalize_story_text(story).split()
    if not tokens:
        return []

    alias_occurrences: list[_AliasOccurrence] = []
    for asset in assets:
        aliases = _token_sequences([asset.word, *asset.aliases])
        for alias in aliases:
            for start, end in _sequence_occurrences(tokens, alias):
                alias_occurrences.append(
                    _AliasOccurrence(start, end, asset.id, len(alias))
                )

    relation_occurrences: list[_RelationOccurrence] = []
    for relation, phrases in _RELATION_PHRASES.items():
        for phrase in _token_sequences(phrases):
            for start, end in _sequence_occurrences(tokens, phrase):
                relation_occurrences.append(
                    _RelationOccurrence(start, end, relation, len(phrase))
                )

    relation_occurrences.sort(key=lambda item: (item.start, -item.length))
    found: list[SpatialRelation] = []
    seen: set[tuple[str, str, str]] = set()

    for occurrence in relation_occurrences:
        left = [
            alias
            for alias in alias_occurrences
            if alias.end <= occurrence.start and occurrence.start - alias.end <= 5
        ]
        right = [
            alias
            for alias in alias_occurrences
            if alias.start >= occurrence.end and alias.start - occurrence.end <= 4
        ]
        if not left or not right:
            continue

        subject = max(left, key=lambda item: (item.end, item.length))
        reference = min(right, key=lambda item: (item.start, -item.length))
        if subject.asset_id == reference.asset_id:
            continue

        key = (subject.asset_id, occurrence.relation, reference.asset_id)
        if key in seen:
            continue
        seen.add(key)
        found.append(
            SpatialRelation(
                subject_asset_id=subject.asset_id,
                relation=occurrence.relation,
                reference_asset_id=reference.asset_id,
            )
        )

    return found


@lru_cache(maxsize=128)
def load_local_bounds(path: str) -> LocalBounds:
    glyph_path = Path(path)
    payload = json.loads(glyph_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"glyph-state must be a non-empty list: {glyph_path}")

    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for item in payload:
        x = float(item["x"])
        y = float(item["y"])
        radius = max(1.0, float(item.get("font_size", 1.0)) * 0.58)
        min_x = min(min_x, x - radius)
        max_x = max(max_x, x + radius)
        min_y = min(min_y, y - radius)
        max_y = max(max_y, y + radius)
    return LocalBounds(min_x, min_y, max_x, max_y)


def transformed_bounds(asset: AssetSpec, transform: SceneTransform) -> CanvasBounds:
    local = load_local_bounds(str(asset.glyphs_path.resolve()))
    return CanvasBounds(
        left=transform.x + local.min_x * transform.scale_x,
        top=transform.y + local.min_y * transform.scale_y,
        right=transform.x + local.max_x * transform.scale_x,
        bottom=transform.y + local.max_y * transform.scale_y,
    )


def _centered_transform(
    asset: AssetSpec,
    transform: SceneTransform,
    *,
    center_x: float,
    center_y: float,
) -> SceneTransform:
    local = load_local_bounds(str(asset.glyphs_path.resolve()))
    return transform.model_copy(
        update={
            "x": center_x - local.center_x * transform.scale_x,
            "y": center_y - local.center_y * transform.scale_y,
        }
    )


def _clamp_transform(
    asset: AssetSpec,
    transform: SceneTransform,
    *,
    canvas_width: int,
    canvas_height: int,
    margin: float,
) -> SceneTransform:
    bounds = transformed_bounds(asset, transform)
    dx = 0.0
    dy = 0.0
    if bounds.left < margin:
        dx = margin - bounds.left
    elif bounds.right > canvas_width - margin:
        dx = canvas_width - margin - bounds.right
    if bounds.top < margin:
        dy = margin - bounds.top
    elif bounds.bottom > canvas_height - margin:
        dy = canvas_height - margin - bounds.bottom
    return transform.model_copy(update={"x": transform.x + dx, "y": transform.y + dy})


def apply_spatial_relations(
    assets: Sequence[AssetSpec],
    relations: Sequence[SpatialRelation],
    *,
    canvas_width: int,
    canvas_height: int,
) -> dict[str, SceneTransform]:
    """Return transforms positioned from measured glyph bounds and explicit relations."""
    by_id = {asset.id: asset for asset in assets}
    transforms = {
        asset.id: asset.transform.model_copy(deep=True)
        for asset in assets
    }
    margin = max(12.0, min(canvas_width, canvas_height) * 0.025)
    gap = max(20.0, min(canvas_width, canvas_height) * 0.045)

    for _ in range(2):
        for relation in relations:
            subject = by_id.get(relation.subject_asset_id)
            reference = by_id.get(relation.reference_asset_id)
            if subject is None or reference is None:
                continue

            current = transforms[subject.id]
            reference_bounds = transformed_bounds(reference, transforms[reference.id])
            subject_bounds = transformed_bounds(subject, current)

            if relation.relation == "above":
                center_x = reference_bounds.center_x
                center_y = reference_bounds.top - gap - subject_bounds.height / 2.0
            elif relation.relation == "below":
                center_x = reference_bounds.center_x
                center_y = reference_bounds.bottom + gap + subject_bounds.height / 2.0
            elif relation.relation == "left_of":
                center_x = reference_bounds.left - gap - subject_bounds.width / 2.0
                center_y = reference_bounds.center_y
            elif relation.relation == "right_of":
                center_x = reference_bounds.right + gap + subject_bounds.width / 2.0
                center_y = reference_bounds.center_y
            else:
                room_right = canvas_width - reference_bounds.right
                room_left = reference_bounds.left
                place_right = room_right >= room_left
                center_x = (
                    reference_bounds.right + gap + subject_bounds.width / 2.0
                    if place_right
                    else reference_bounds.left - gap - subject_bounds.width / 2.0
                )
                center_y = reference_bounds.center_y

            positioned = _centered_transform(
                subject,
                current,
                center_x=center_x,
                center_y=center_y,
            )
            transforms[subject.id] = _clamp_transform(
                subject,
                positioned,
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                margin=margin,
            )

    return transforms


def orient_for_direction(
    asset: AssetSpec,
    transform: SceneTransform,
    direction: str,
) -> SceneTransform:
    """Mirror glyph positions when movement opposes the source silhouette facing."""
    if direction not in {"left", "right"} or asset.facing == "neutral":
        return transform
    mirror = asset.facing != direction
    return transform.model_copy(update={"mirror_x": mirror})
