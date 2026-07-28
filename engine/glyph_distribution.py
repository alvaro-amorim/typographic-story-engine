from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import List, Literal, Tuple

from engine.models import Glyph

ValidCoordinate = Tuple[int, int, float]
ZoneName = Literal["edge", "mid", "core"]
ZONE_NAMES: tuple[ZoneName, ...] = ("edge", "mid", "core")


@dataclass(frozen=True)
class DistributionConfig:
    """Controls how glyphs are distributed across the object silhouette."""

    edge_threshold: float = 0.18
    mid_threshold: float = 0.55
    edge_ratio: float = 0.45
    mid_ratio: float = 0.35
    core_ratio: float = 0.20
    cell_size: int = 8
    edge_capacity: int = 4
    mid_capacity: int = 3
    core_capacity: int = 2

    def __post_init__(self) -> None:
        if not 0.0 < self.edge_threshold < self.mid_threshold < 1.0:
            raise ValueError(
                "depth thresholds must satisfy 0 < edge_threshold < "
                "mid_threshold < 1"
            )

        ratios = self.zone_ratios
        if any(ratio < 0.0 for ratio in ratios.values()):
            raise ValueError("zone ratios cannot be negative")
        if math.isclose(sum(ratios.values()), 0.0):
            raise ValueError("at least one zone ratio must be greater than zero")

        if self.cell_size <= 0:
            raise ValueError("cell_size must be greater than zero")
        if any(capacity <= 0 for capacity in self.zone_capacities.values()):
            raise ValueError("zone capacities must be greater than zero")

    @property
    def zone_ratios(self) -> dict[ZoneName, float]:
        return {
            "edge": self.edge_ratio,
            "mid": self.mid_ratio,
            "core": self.core_ratio,
        }

    @property
    def zone_capacities(self) -> dict[ZoneName, int]:
        return {
            "edge": self.edge_capacity,
            "mid": self.mid_capacity,
            "core": self.core_capacity,
        }


def classify_depth_zone(
    depth: float,
    edge_threshold: float,
    mid_threshold: float,
) -> ZoneName:
    """Classify a normalized distance value into edge, mid or core."""
    normalized = max(0.0, min(1.0, float(depth)))
    if normalized <= edge_threshold:
        return "edge"
    if normalized <= mid_threshold:
        return "mid"
    return "core"


def split_glyph_budget(
    glyph_count: int,
    zone_ratios: Mapping[ZoneName, float],
) -> dict[ZoneName, int]:
    """Split a glyph total exactly using the largest-remainder method."""
    if glyph_count <= 0:
        raise ValueError("glyph_count must be greater than zero")

    ratios = {zone: float(zone_ratios.get(zone, 0.0)) for zone in ZONE_NAMES}
    if any(ratio < 0.0 for ratio in ratios.values()):
        raise ValueError("zone ratios cannot be negative")

    ratio_total = sum(ratios.values())
    if ratio_total <= 0.0:
        raise ValueError("at least one zone ratio must be greater than zero")

    raw = {
        zone: glyph_count * ratio / ratio_total
        for zone, ratio in ratios.items()
    }
    budget = {zone: math.floor(raw[zone]) for zone in ZONE_NAMES}
    remaining = glyph_count - sum(budget.values())

    remainder_order = sorted(
        ZONE_NAMES,
        key=lambda zone: (raw[zone] - budget[zone], -ZONE_NAMES.index(zone)),
        reverse=True,
    )
    for zone in remainder_order[:remaining]:
        budget[zone] += 1

    return budget


def _redistribute_empty_zone_budgets(
    budgets: dict[ZoneName, int],
    coordinates_by_zone: Mapping[ZoneName, Sequence[ValidCoordinate]],
    ratios: Mapping[ZoneName, float],
) -> dict[ZoneName, int]:
    result = dict(budgets)
    missing = sum(
        result[zone]
        for zone in ZONE_NAMES
        if not coordinates_by_zone[zone]
    )

    for zone in ZONE_NAMES:
        if not coordinates_by_zone[zone]:
            result[zone] = 0

    if missing == 0:
        return result

    available_ratios = {
        zone: ratios[zone] if coordinates_by_zone[zone] else 0.0
        for zone in ZONE_NAMES
    }
    if sum(available_ratios.values()) <= 0.0:
        available_ratios = {
            zone: 1.0 if coordinates_by_zone[zone] else 0.0
            for zone in ZONE_NAMES
        }

    redistributed = split_glyph_budget(missing, available_ratios)
    for zone in ZONE_NAMES:
        result[zone] += redistributed[zone]
    return result


def _build_spatial_buckets(
    coordinates: Sequence[ValidCoordinate],
    cell_size: int,
) -> dict[tuple[int, int], list[ValidCoordinate]]:
    buckets: dict[tuple[int, int], list[ValidCoordinate]] = defaultdict(list)
    for coordinate in coordinates:
        x, y, _ = coordinate
        buckets[(x // cell_size, y // cell_size)].append(coordinate)
    return dict(buckets)


def _choose_effective_cell_size(
    coordinates: Sequence[ValidCoordinate],
    target_count: int,
    requested_cell_size: int,
    capacity: int,
) -> int:
    """Reduce the cell size when needed so the spatial cap can satisfy a zone."""
    unique_target = min(target_count, len(coordinates))
    cell_size = requested_cell_size

    while cell_size > 1:
        cell_count = len(_build_spatial_buckets(coordinates, cell_size))
        if cell_count * capacity >= unique_target:
            break
        cell_size -= 1

    return cell_size


def sample_zone_coordinates(
    coordinates: Sequence[ValidCoordinate],
    target_count: int,
    rng: random.Random,
    cell_size: int,
    capacity: int,
) -> list[ValidCoordinate]:
    """Select spatially spread coordinates using deterministic cell round-robin.

    The configured capacity is a hard cap while unique coordinates are available.
    The cell size is reduced automatically when a zone needs more spatial slots.
    Only when ``target_count`` exceeds the number of unique pixels are positions
    reused, preserving the requested glyph total for very small masks.
    """
    if target_count < 0:
        raise ValueError("target_count cannot be negative")
    if target_count == 0:
        return []
    if not coordinates:
        raise ValueError("coordinates cannot be empty when target_count is positive")
    if cell_size <= 0 or capacity <= 0:
        raise ValueError("cell_size and capacity must be greater than zero")

    effective_cell_size = _choose_effective_cell_size(
        coordinates,
        target_count,
        cell_size,
        capacity,
    )
    buckets = _build_spatial_buckets(coordinates, effective_cell_size)
    cell_keys = list(buckets)
    rng.shuffle(cell_keys)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    selected: list[ValidCoordinate] = []
    for _ in range(capacity):
        active_cells = [cell for cell in cell_keys if buckets[cell]]
        rng.shuffle(active_cells)
        for cell in active_cells:
            selected.append(buckets[cell].pop())
            if len(selected) == min(target_count, len(coordinates)):
                break
        if len(selected) == min(target_count, len(coordinates)):
            break

    # At cell_size=1 a capacity greater than one cannot add unique coordinates
    # from the same pixel. Fill any remaining unique quota without clustering
    # rules, which is still preferable to duplicating coordinates.
    if len(selected) < min(target_count, len(coordinates)):
        remaining = [coordinate for bucket in buckets.values() for coordinate in bucket]
        rng.shuffle(remaining)
        selected.extend(
            remaining[: min(target_count, len(coordinates)) - len(selected)]
        )

    if len(selected) < target_count:
        reusable = selected or list(coordinates)
        while len(selected) < target_count:
            selected.append(rng.choice(reusable))

    return selected


def _interpolate(start: float, end: float, amount: float) -> float:
    clamped = max(0.0, min(1.0, amount))
    return start + (end - start) * clamped


def _zone_progress(
    zone: ZoneName,
    depth: float,
    config: DistributionConfig,
) -> float:
    if zone == "edge":
        return depth / config.edge_threshold
    if zone == "mid":
        return (depth - config.edge_threshold) / (
            config.mid_threshold - config.edge_threshold
        )
    return (depth - config.mid_threshold) / (1.0 - config.mid_threshold)


def _font_size_for_zone(
    zone: ZoneName,
    depth: float,
    font_size_range: Tuple[float, float],
    config: DistributionConfig,
    rng: random.Random,
) -> float:
    minimum, maximum = font_size_range
    span = maximum - minimum
    progress = _zone_progress(zone, depth, config)

    ranges = {
        "edge": (minimum, minimum + span * 0.30),
        "mid": (minimum + span * 0.12, minimum + span * 0.58),
        "core": (minimum + span * 0.25, minimum + span * 0.72),
    }
    zone_minimum, zone_maximum = ranges[zone]
    base_size = _interpolate(zone_minimum, zone_maximum, progress)
    variance = max(0.35, base_size * 0.08)
    return max(minimum, min(maximum, rng.uniform(base_size - variance, base_size + variance)))


def _opacity_for_zone(
    zone: ZoneName,
    depth: float,
    config: DistributionConfig,
    rng: random.Random,
) -> float:
    progress = _zone_progress(zone, depth, config)
    ranges = {
        "edge": (0.98, 0.82),
        "mid": (0.78, 0.58),
        "core": (0.56, 0.42),
    }
    start, end = ranges[zone]
    base_opacity = _interpolate(start, end, progress)
    return max(0.0, min(1.0, base_opacity + rng.uniform(-0.035, 0.035)))


def distribute_glyphs(
    object_id: str,
    valid_coords: Sequence[ValidCoordinate],
    character_sequence: Sequence[str],
    glyph_count: int,
    font_size_range: Tuple[float, float],
    palette: Sequence[str],
    seed: int = 42,
    rotation_range: Tuple[float, float] = (-12.0, 12.0),
    distribution_config: DistributionConfig | None = None,
) -> List[Glyph]:
    """Create deterministic, shape-aware glyphs without mutating global RNG state."""
    if not valid_coords:
        raise ValueError("valid_coords cannot be empty")
    if not character_sequence:
        raise ValueError("character_sequence cannot be empty")
    if not palette:
        raise ValueError("palette cannot be empty")
    if glyph_count <= 0:
        raise ValueError("glyph_count must be greater than zero")

    min_size, max_size = font_size_range
    if min_size <= 0 or max_size <= 0 or min_size > max_size:
        raise ValueError("font_size_range must contain positive ascending values")

    min_rotation, max_rotation = rotation_range
    if min_rotation > max_rotation:
        raise ValueError("rotation_range minimum cannot exceed maximum")

    config = distribution_config or DistributionConfig()
    rng = random.Random(seed)

    coordinates_by_zone: dict[ZoneName, list[ValidCoordinate]] = {
        zone: [] for zone in ZONE_NAMES
    }
    for coordinate in valid_coords:
        x, y, distance = coordinate
        normalized_distance = max(0.0, min(1.0, float(distance)))
        zone = classify_depth_zone(
            normalized_distance,
            config.edge_threshold,
            config.mid_threshold,
        )
        coordinates_by_zone[zone].append((x, y, normalized_distance))

    budgets = split_glyph_budget(glyph_count, config.zone_ratios)
    budgets = _redistribute_empty_zone_budgets(
        budgets,
        coordinates_by_zone,
        config.zone_ratios,
    )

    glyphs: List[Glyph] = []
    index = 0
    for zone in ZONE_NAMES:
        zone_budget = budgets[zone]
        if zone_budget == 0:
            continue

        selected_coordinates = sample_zone_coordinates(
            coordinates_by_zone[zone],
            zone_budget,
            rng,
            config.cell_size,
            config.zone_capacities[zone],
        )

        for x, y, normalized_distance in selected_coordinates:
            glyphs.append(
                Glyph(
                    id=f"{object_id}_glyph_{index}",
                    object_id=object_id,
                    character=rng.choice(character_sequence),
                    x=float(x),
                    y=float(y),
                    rotation=rng.uniform(min_rotation, max_rotation),
                    font_size=float(
                        _font_size_for_zone(
                            zone,
                            normalized_distance,
                            font_size_range,
                            config,
                            rng,
                        )
                    ),
                    opacity=float(
                        _opacity_for_zone(
                            zone,
                            normalized_distance,
                            config,
                            rng,
                        )
                    ),
                    color=rng.choice(palette),
                    zone=zone,
                    depth=normalized_distance,
                )
            )
            index += 1

    # Core is painted first and the precise edge layer last, keeping the
    # silhouette readable even when glyphs overlap.
    zone_render_order = {"core": 0, "mid": 1, "edge": 2}
    glyphs.sort(
        key=lambda glyph: (
            zone_render_order[glyph.zone],
            -glyph.font_size,
            glyph.id,
        )
    )
    return glyphs
