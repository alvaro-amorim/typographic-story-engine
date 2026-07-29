from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from statistics import fmean
from typing import Tuple

from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    OrientationField,
    ValidCoordinate,
    _rotation_for_glyph,
    classify_depth_zone,
    sample_zone_coordinates,
)
from engine.layered_distribution import split_layer_budget
from engine.models import Glyph
from engine.organic_styling import STYLE_ROLE_ORDER, StyleRole, organic_modulation


@dataclass(frozen=True)
class BalancedStyleConfig:
    """Blend organic outlines with a spatially controlled layered interior."""

    outline_ratio: float = 0.34
    fill_ratio: float = 0.56
    texture_ratio: float = 0.10

    outline_shadow_fraction: float = 0.26
    outline_detail_depth_max: float = 0.105
    outline_shadow_depth_min: float = 0.050
    outline_depth_max: float = 0.18
    fill_depth_min: float = 0.035
    texture_depth_min: float = 0.24

    detail_cell_size: int = 5
    shadow_cell_size: int = 8
    fill_cell_size: int = 10
    texture_cell_size: int = 16

    detail_capacity: int = 2
    shadow_capacity: int = 1
    fill_capacity: int = 1
    texture_capacity: int = 1

    organic_scale: float = 0.032
    outline_coherence: float = 0.48
    fill_modulation_strength: float = 0.12
    fill_opacity_min: float = 0.42
    fill_opacity_max: float = 0.57
    fill_dark_probability: float = 0.08
    texture_opacity_min: float = 0.21
    texture_opacity_max: float = 0.28
    metric_cell_size: int = 32

    def __post_init__(self) -> None:
        ratios = self.layer_ratios
        if any(ratio < 0.0 for ratio in ratios.values()):
            raise ValueError("layer ratios cannot be negative")
        if math.isclose(sum(ratios.values()), 0.0):
            raise ValueError("at least one layer ratio must be greater than zero")
        if not 0.0 <= self.outline_shadow_fraction <= 1.0:
            raise ValueError("outline_shadow_fraction must be between zero and one")
        if not 0.0 < self.outline_detail_depth_max <= self.outline_depth_max < 1.0:
            raise ValueError(
                "outline depths must satisfy 0 < detail_depth_max <= outline_depth_max < 1"
            )
        if not 0.0 <= self.outline_shadow_depth_min < self.outline_depth_max:
            raise ValueError("outline_shadow_depth_min must be below outline_depth_max")
        if not 0.0 <= self.fill_depth_min < 1.0:
            raise ValueError("fill_depth_min must be between zero inclusive and one exclusive")
        if not 0.0 <= self.texture_depth_min < 1.0:
            raise ValueError(
                "texture_depth_min must be between zero inclusive and one exclusive"
            )
        if any(value <= 0 for value in self.role_cell_sizes.values()):
            raise ValueError("role cell sizes must be greater than zero")
        if any(value <= 0 for value in self.role_capacities.values()):
            raise ValueError("role capacities must be greater than zero")
        if self.organic_scale <= 0.0:
            raise ValueError("organic_scale must be greater than zero")
        if not 0.0 <= self.outline_coherence <= 1.0:
            raise ValueError("outline_coherence must be between zero and one")
        if not 0.0 <= self.fill_modulation_strength <= 1.0:
            raise ValueError("fill_modulation_strength must be between zero and one")
        if not 0.0 <= self.fill_opacity_min <= self.fill_opacity_max <= 1.0:
            raise ValueError(
                "fill opacity bounds must satisfy 0 <= minimum <= maximum <= 1"
            )
        if not 0.0 <= self.fill_dark_probability <= 1.0:
            raise ValueError("fill_dark_probability must be between zero and one")
        if not 0.0 <= self.texture_opacity_min <= self.texture_opacity_max <= 1.0:
            raise ValueError(
                "texture opacity bounds must satisfy 0 <= minimum <= maximum <= 1"
            )
        if self.metric_cell_size <= 0:
            raise ValueError("metric_cell_size must be greater than zero")

    @property
    def layer_ratios(self) -> dict[str, float]:
        return {
            "outline": self.outline_ratio,
            "fill": self.fill_ratio,
            "texture": self.texture_ratio,
        }

    @property
    def role_cell_sizes(self) -> dict[StyleRole, int]:
        return {
            "outline_detail": self.detail_cell_size,
            "outline_shadow": self.shadow_cell_size,
            "fill_mass": self.fill_cell_size,
            "texture_accent": self.texture_cell_size,
        }

    @property
    def role_capacities(self) -> dict[StyleRole, int]:
        return {
            "outline_detail": self.detail_capacity,
            "outline_shadow": self.shadow_capacity,
            "fill_mass": self.fill_capacity,
            "texture_accent": self.texture_capacity,
        }


def split_balanced_role_budget(
    glyph_count: int,
    config: BalancedStyleConfig,
) -> dict[StyleRole, int]:
    layer_budget = split_layer_budget(glyph_count, config.layer_ratios)
    shadow = int(round(layer_budget["outline"] * config.outline_shadow_fraction))
    shadow = max(0, min(layer_budget["outline"], shadow))
    return {
        "outline_shadow": shadow,
        "outline_detail": layer_budget["outline"] - shadow,
        "fill_mass": layer_budget["fill"],
        "texture_accent": layer_budget["texture"],
    }


def build_balanced_coordinate_pools(
    valid_coords: Sequence[ValidCoordinate],
    config: BalancedStyleConfig,
) -> dict[StyleRole, list[ValidCoordinate]]:
    if not valid_coords:
        raise ValueError("valid_coords cannot be empty")

    coordinates = [
        (int(x), int(y), max(0.0, min(1.0, float(depth))))
        for x, y, depth in valid_coords
    ]
    pools: dict[StyleRole, list[ValidCoordinate]] = {
        "outline_detail": [
            coordinate
            for coordinate in coordinates
            if coordinate[2] <= config.outline_detail_depth_max
        ],
        "outline_shadow": [
            coordinate
            for coordinate in coordinates
            if config.outline_shadow_depth_min
            <= coordinate[2]
            <= config.outline_depth_max
        ],
        "fill_mass": [
            coordinate
            for coordinate in coordinates
            if coordinate[2] >= config.fill_depth_min
        ],
        "texture_accent": [
            coordinate
            for coordinate in coordinates
            if coordinate[2] >= config.texture_depth_min
        ],
    }

    if not pools["outline_detail"]:
        shallowest = min(coordinate[2] for coordinate in coordinates)
        pools["outline_detail"] = [
            coordinate
            for coordinate in coordinates
            if coordinate[2] <= shallowest + 0.035
        ]
    if not pools["outline_shadow"]:
        pools["outline_shadow"] = [
            coordinate
            for coordinate in coordinates
            if coordinate[2] <= config.outline_depth_max
        ]
    if not pools["fill_mass"]:
        pools["fill_mass"] = list(coordinates)
    if not pools["texture_accent"]:
        deepest = sorted(coordinates, key=lambda coordinate: coordinate[2], reverse=True)
        pools["texture_accent"] = deepest[: max(1, len(deepest) // 5)]

    return pools


def _sample_outline_coordinates(
    coordinates: Sequence[ValidCoordinate],
    target_count: int,
    rng: random.Random,
    cell_size: int,
    capacity: int,
    seed: int,
    scale: float,
    salt: int,
    coherence: float,
) -> list[ValidCoordinate]:
    if target_count == 0:
        return []
    candidate_count = min(
        len(coordinates),
        max(target_count, math.ceil(target_count * 1.55)),
    )
    candidates = sample_zone_coordinates(
        coordinates,
        candidate_count,
        rng,
        cell_size,
        capacity,
    )
    scored: list[tuple[float, ValidCoordinate]] = []
    for coordinate in candidates:
        x, y, _ = coordinate
        modulation = organic_modulation(x, y, seed, scale, salt)
        score = modulation * coherence + rng.random() * (1.0 - coherence)
        scored.append((score, coordinate))
    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [coordinate for _, coordinate in scored[:target_count]]
    reusable = selected or list(coordinates)
    while len(selected) < target_count:
        selected.append(rng.choice(reusable))
    rng.shuffle(selected)
    return selected


def _micro_modulation(raw: float, strength: float) -> float:
    return max(0.0, min(1.0, 0.5 + (raw - 0.5) * strength))


def _role_orientation(
    role: StyleRole,
    orientation: OrientationConfig,
) -> OrientationConfig:
    multipliers = {
        "outline_detail": (1.00, 0.50),
        "outline_shadow": (0.66, 0.86),
        "fill_mass": (0.26, 1.18),
        "texture_accent": (0.00, 1.70),
    }
    strength, jitter = multipliers[role]
    return replace(
        orientation,
        enabled=orientation.enabled and strength > 0.0,
        edge_strength=min(1.0, orientation.edge_strength * strength),
        mid_strength=min(1.0, orientation.mid_strength * strength),
        core_strength=min(1.0, orientation.core_strength * strength),
        jitter_degrees=orientation.jitter_degrees * jitter,
    )


def _role_font_size(
    role: StyleRole,
    depth: float,
    modulation: float,
    font_size_range: Tuple[float, float],
    config: BalancedStyleConfig,
    rng: random.Random,
) -> float:
    minimum, maximum = font_size_range
    span = maximum - minimum

    if role == "outline_detail":
        progress = depth / max(config.outline_detail_depth_max, 1e-12)
        base = minimum + span * (0.03 + 0.19 * progress)
        base *= 0.88 + modulation * 0.20
        variance = max(0.20, base * 0.055)
    elif role == "outline_shadow":
        progress = (depth - config.outline_shadow_depth_min) / max(
            1e-12,
            config.outline_depth_max - config.outline_shadow_depth_min,
        )
        base = minimum + span * (0.13 + 0.27 * progress)
        base *= 0.91 + modulation * 0.16
        variance = max(0.25, base * 0.07)
    elif role == "texture_accent":
        progress = (depth - config.texture_depth_min) / max(
            1e-12,
            1.0 - config.texture_depth_min,
        )
        base = minimum + span * (0.04 + 0.20 * progress)
        variance = max(0.24, base * 0.085)
    else:
        progress = (depth - config.fill_depth_min) / max(
            1e-12,
            1.0 - config.fill_depth_min,
        )
        base = minimum + span * (0.12 + 0.48 * progress)
        base *= 0.97 + modulation * 0.06
        variance = max(0.25, base * 0.065)

    return max(minimum, min(maximum, rng.uniform(base - variance, base + variance)))


def _role_opacity(
    role: StyleRole,
    depth: float,
    modulation: float,
    config: BalancedStyleConfig,
    rng: random.Random,
) -> float:
    if role == "outline_detail":
        progress = depth / max(config.outline_detail_depth_max, 1e-12)
        base = 0.82 + modulation * 0.14 - progress * 0.025
        variance = 0.025
    elif role == "outline_shadow":
        progress = (depth - config.outline_shadow_depth_min) / max(
            1e-12,
            config.outline_depth_max - config.outline_shadow_depth_min,
        )
        base = 0.43 + modulation * 0.17 - progress * 0.035
        variance = 0.030
    elif role == "texture_accent":
        base = config.texture_opacity_min + (
            config.texture_opacity_max - config.texture_opacity_min
        ) * modulation
        variance = 0.018
    else:
        progress = (depth - config.fill_depth_min) / max(
            1e-12,
            1.0 - config.fill_depth_min,
        )
        depth_base = config.fill_opacity_max + (
            config.fill_opacity_min - config.fill_opacity_max
        ) * progress
        base = depth_base + (modulation - 0.5) * 0.10
        variance = 0.024

    return max(0.0, min(1.0, base + rng.uniform(-variance, variance)))


def _choose_color(
    role: StyleRole,
    palette: Sequence[str],
    config: BalancedStyleConfig,
    rng: random.Random,
) -> str:
    if role in {"outline_detail", "outline_shadow"}:
        dark = palette[: max(1, (len(palette) + 1) // 2)]
        return rng.choice(dark)
    if len(palette) == 1:
        return palette[0]
    if role == "fill_mass":
        if rng.random() < config.fill_dark_probability:
            return palette[0]
        return rng.choice(palette[1:])
    return rng.choice(palette[1:])


def distribute_balanced_glyphs(
    object_id: str,
    valid_coords: Sequence[ValidCoordinate],
    character_sequence: Sequence[str],
    glyph_count: int,
    font_size_range: Tuple[float, float],
    palette: Sequence[str],
    seed: int = 42,
    rotation_range: Tuple[float, float] = (-12.0, 12.0),
    distribution_config: DistributionConfig | None = None,
    orientation_field: OrientationField | None = None,
    orientation_config: OrientationConfig | None = None,
    style_config: BalancedStyleConfig | None = None,
) -> list[Glyph]:
    """Use organic outline variation with a clean, mass-limited interior."""
    if not valid_coords:
        raise ValueError("valid_coords cannot be empty")
    if not character_sequence:
        raise ValueError("character_sequence cannot be empty")
    if not palette:
        raise ValueError("palette cannot be empty")
    if glyph_count <= 0:
        raise ValueError("glyph_count must be greater than zero")
    minimum, maximum = font_size_range
    if minimum <= 0 or maximum <= 0 or minimum > maximum:
        raise ValueError("font_size_range must contain positive ascending values")
    if rotation_range[0] > rotation_range[1]:
        raise ValueError("rotation_range minimum cannot exceed maximum")

    distribution = distribution_config or DistributionConfig()
    orientation = orientation_config or OrientationConfig()
    config = style_config or BalancedStyleConfig()
    rng = random.Random(seed)
    pools = build_balanced_coordinate_pools(valid_coords, config)
    budgets = split_balanced_role_budget(glyph_count, config)
    salts: dict[StyleRole, int] = {
        "outline_detail": 11,
        "outline_shadow": 29,
        "fill_mass": 47,
        "texture_accent": 71,
    }

    glyphs: list[Glyph] = []
    index = 0
    for role in STYLE_ROLE_ORDER:
        budget = budgets[role]
        if budget == 0:
            continue

        if role in {"outline_detail", "outline_shadow"}:
            selected = _sample_outline_coordinates(
                pools[role],
                budget,
                rng,
                config.role_cell_sizes[role],
                config.role_capacities[role],
                seed,
                config.organic_scale,
                salts[role],
                config.outline_coherence,
            )
        else:
            selected = sample_zone_coordinates(
                pools[role],
                budget,
                rng,
                config.role_cell_sizes[role],
                config.role_capacities[role],
            )

        role_orientation = _role_orientation(role, orientation)
        layer = {
            "outline_detail": "outline",
            "outline_shadow": "outline",
            "fill_mass": "fill",
            "texture_accent": "texture",
        }[role]

        for x, y, depth in selected:
            zone = classify_depth_zone(
                depth,
                distribution.edge_threshold,
                distribution.mid_threshold,
            )
            raw_modulation = organic_modulation(
                int(x),
                int(y),
                seed,
                config.organic_scale,
                salts[role],
            )
            modulation = (
                raw_modulation
                if role in {"outline_detail", "outline_shadow"}
                else _micro_modulation(raw_modulation, config.fill_modulation_strength)
            )
            (
                rotation,
                orientation_angle,
                orientation_confidence,
                orientation_strength,
                orientation_source,
            ) = _rotation_for_glyph(
                zone=zone,
                depth=depth,
                position=(int(x), int(y)),
                rotation_range=rotation_range,
                distribution_config=distribution,
                orientation_field=orientation_field,
                orientation_config=role_orientation,
                rng=rng,
            )
            glyphs.append(
                Glyph(
                    id=f"{object_id}_balanced_{role}_{index}",
                    object_id=object_id,
                    character=rng.choice(character_sequence),
                    x=float(x),
                    y=float(y),
                    rotation=float(rotation),
                    font_size=float(
                        _role_font_size(
                            role,
                            depth,
                            modulation,
                            font_size_range,
                            config,
                            rng,
                        )
                    ),
                    opacity=float(
                        _role_opacity(
                            role,
                            depth,
                            modulation,
                            config,
                            rng,
                        )
                    ),
                    color=_choose_color(role, palette, config, rng),
                    zone=zone,
                    layer=layer,
                    style_role=role,
                    depth=depth,
                    orientation_angle=orientation_angle,
                    orientation_confidence=orientation_confidence,
                    orientation_strength=orientation_strength,
                    orientation_source=orientation_source,
                )
            )
            index += 1

    render_order = {role: position for position, role in enumerate(STYLE_ROLE_ORDER)}
    glyphs.sort(
        key=lambda glyph: (
            render_order.get(glyph.style_role, len(render_order)),
            -glyph.font_size,
            glyph.id,
        )
    )
    return glyphs


def _max_local_count(glyphs: Sequence[Glyph], cell_size: int) -> int:
    counts: Counter[tuple[int, int]] = Counter(
        (int(glyph.x) // cell_size, int(glyph.y) // cell_size) for glyph in glyphs
    )
    return max(counts.values(), default=0)


def summarize_balanced_metrics(
    glyphs: Sequence[Glyph],
    metric_cell_size: int = 32,
) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for role in STYLE_ROLE_ORDER:
        items = [glyph for glyph in glyphs if glyph.style_role == role]
        summary[role] = {
            "count": len(items),
            "mean_font_size": fmean(glyph.font_size for glyph in items) if items else 0.0,
            "mean_opacity": fmean(glyph.opacity for glyph in items) if items else 0.0,
            "mean_orientation_strength": (
                fmean(glyph.orientation_strength for glyph in items) if items else 0.0
            ),
            "mean_depth": fmean(glyph.depth for glyph in items) if items else 0.0,
            "max_glyphs_per_metric_cell": _max_local_count(items, metric_cell_size),
        }
    return summary
