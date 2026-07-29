from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from statistics import fmean
from typing import Literal, Tuple

from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    OrientationField,
    ValidCoordinate,
    ZoneName,
    _rotation_for_glyph,
    classify_depth_zone,
    sample_zone_coordinates,
)
from engine.layered_distribution import LayerName, split_layer_budget
from engine.models import Glyph

StyleRole = Literal[
    "outline_shadow",
    "outline_detail",
    "fill_mass",
    "texture_accent",
]
STYLE_ROLE_ORDER: tuple[StyleRole, ...] = (
    "texture_accent",
    "fill_mass",
    "outline_shadow",
    "outline_detail",
)


@dataclass(frozen=True)
class OrganicStyleConfig:
    """Art-direction controls layered typography without changing its semantics."""

    outline_ratio: float = 0.34
    fill_ratio: float = 0.54
    texture_ratio: float = 0.12

    outline_shadow_fraction: float = 0.32
    outline_detail_depth_max: float = 0.105
    outline_shadow_depth_min: float = 0.045
    outline_depth_max: float = 0.18
    fill_depth_min: float = 0.035
    texture_depth_min: float = 0.20

    detail_cell_size: int = 5
    shadow_cell_size: int = 7
    fill_cell_size: int = 9
    texture_cell_size: int = 15

    detail_capacity: int = 2
    shadow_capacity: int = 2
    fill_capacity: int = 2
    texture_capacity: int = 1

    organic_scale: float = 0.032
    texture_opacity_min: float = 0.20
    texture_opacity_max: float = 0.31

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
            raise ValueError(
                "outline_shadow_depth_min must be below outline_depth_max"
            )
        if not 0.0 <= self.fill_depth_min < 1.0:
            raise ValueError(
                "fill_depth_min must be between zero inclusive and one exclusive"
            )
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
        if not 0.0 <= self.texture_opacity_min <= self.texture_opacity_max <= 1.0:
            raise ValueError(
                "texture opacity bounds must satisfy 0 <= minimum <= maximum <= 1"
            )

    @property
    def layer_ratios(self) -> dict[LayerName, float]:
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


def split_style_role_budget(
    glyph_count: int,
    config: OrganicStyleConfig,
) -> dict[StyleRole, int]:
    """Split the exact total into texture, fill and two complementary outlines."""
    layer_budget = split_layer_budget(glyph_count, config.layer_ratios)
    shadow = int(round(layer_budget["outline"] * config.outline_shadow_fraction))
    shadow = max(0, min(layer_budget["outline"], shadow))
    detail = layer_budget["outline"] - shadow
    return {
        "outline_shadow": shadow,
        "outline_detail": detail,
        "fill_mass": layer_budget["fill"],
        "texture_accent": layer_budget["texture"],
    }


def build_organic_coordinate_pools(
    valid_coords: Sequence[ValidCoordinate],
    config: OrganicStyleConfig,
) -> dict[StyleRole, list[ValidCoordinate]]:
    """Return overlapping pools for variable outline thickness and interior roles."""
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
        deepest = sorted(
            coordinates,
            key=lambda coordinate: coordinate[2],
            reverse=True,
        )
        pools["texture_accent"] = deepest[: max(1, len(deepest) // 5)]

    return pools


def _hash01(x: int, y: int, seed: int, salt: int) -> float:
    value = (
        (int(x) * 374_761_393)
        + (int(y) * 668_265_263)
        + (int(seed) * 69_069)
        + (int(salt) * 362_437)
    ) & 0xFFFFFFFF
    value = ((value ^ (value >> 13)) * 1_274_126_177) & 0xFFFFFFFF
    value ^= value >> 16
    return (value & 0xFFFFFFFF) / 0xFFFFFFFF


def organic_modulation(
    x: int,
    y: int,
    seed: int,
    scale: float = 0.032,
    salt: int = 0,
) -> float:
    """Stable low-frequency modulation used to avoid mechanically uniform bands."""
    phase = seed * 0.000_137 + salt * 0.731
    first = 0.5 + 0.5 * math.sin((x * scale) + (y * scale * 0.61) + phase)
    second = 0.5 + 0.5 * math.sin(
        (x * scale * 0.37) - (y * scale * 1.23) + phase * 1.7
    )
    low_frequency = (first * 0.62) + (second * 0.38)
    hashed = _hash01(x, y, seed, salt)
    return max(0.0, min(1.0, low_frequency * 0.78 + hashed * 0.22))


def _sample_organic_coordinates(
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

    unique_target = min(
        len(coordinates),
        max(target_count, math.ceil(target_count * 1.75)),
    )
    candidates = sample_zone_coordinates(
        coordinates,
        unique_target,
        rng,
        cell_size,
        capacity,
    )
    scored: list[tuple[float, ValidCoordinate]] = []
    for coordinate in candidates:
        x, y, _ = coordinate
        modulation = organic_modulation(x, y, seed, scale, salt)
        score = (modulation * coherence) + (rng.random() * (1.0 - coherence))
        scored.append((score, coordinate))
    scored.sort(key=lambda item: item[0], reverse=True)

    selected = [coordinate for _, coordinate in scored[:target_count]]
    reusable = selected or list(coordinates)
    while len(selected) < target_count:
        selected.append(rng.choice(reusable))
    rng.shuffle(selected)
    return selected


def _interpolate(start: float, end: float, amount: float) -> float:
    clamped = max(0.0, min(1.0, float(amount)))
    return start + (end - start) * clamped


def _role_font_size(
    role: StyleRole,
    depth: float,
    modulation: float,
    font_size_range: Tuple[float, float],
    config: OrganicStyleConfig,
    rng: random.Random,
) -> float:
    minimum, maximum = font_size_range
    span = maximum - minimum

    if role == "outline_detail":
        progress = depth / max(config.outline_detail_depth_max, 1e-12)
        base = _interpolate(minimum, minimum + span * 0.22, progress)
        base *= 0.82 + modulation * 0.28
        variance = max(0.22, base * 0.07)
    elif role == "outline_shadow":
        progress = (depth - config.outline_shadow_depth_min) / max(
            1e-12,
            config.outline_depth_max - config.outline_shadow_depth_min,
        )
        base = _interpolate(
            minimum + span * 0.12,
            minimum + span * 0.42,
            progress,
        )
        base *= 0.86 + modulation * 0.24
        variance = max(0.28, base * 0.09)
    elif role == "texture_accent":
        progress = (depth - config.texture_depth_min) / max(
            1e-12,
            1.0 - config.texture_depth_min,
        )
        base = _interpolate(minimum, minimum + span * 0.30, progress)
        base *= 0.80 + modulation * 0.38
        variance = max(0.30, base * 0.14)
    else:
        progress = (depth - config.fill_depth_min) / max(
            1e-12,
            1.0 - config.fill_depth_min,
        )
        base = _interpolate(
            minimum + span * 0.10,
            minimum + span * 0.68,
            progress,
        )
        base *= 0.80 + modulation * 0.36
        variance = max(0.32, base * 0.13)

    return max(
        minimum,
        min(maximum, rng.uniform(base - variance, base + variance)),
    )


def _role_opacity(
    role: StyleRole,
    depth: float,
    modulation: float,
    config: OrganicStyleConfig,
    rng: random.Random,
) -> float:
    if role == "outline_detail":
        progress = depth / max(config.outline_detail_depth_max, 1e-12)
        base = 0.78 + modulation * 0.20 - progress * 0.035
        variance = 0.035
    elif role == "outline_shadow":
        progress = (depth - config.outline_shadow_depth_min) / max(
            1e-12,
            config.outline_depth_max - config.outline_shadow_depth_min,
        )
        base = 0.43 + modulation * 0.27 - progress * 0.04
        variance = 0.045
    elif role == "texture_accent":
        base = _interpolate(
            config.texture_opacity_min,
            config.texture_opacity_max,
            modulation,
        )
        variance = 0.025
    else:
        progress = (depth - config.fill_depth_min) / max(
            1e-12,
            1.0 - config.fill_depth_min,
        )
        base = 0.43 + modulation * 0.27 - progress * 0.075
        variance = 0.045

    return max(0.0, min(1.0, base + rng.uniform(-variance, variance)))


def _role_layer(role: StyleRole) -> LayerName:
    return {
        "outline_shadow": "outline",
        "outline_detail": "outline",
        "fill_mass": "fill",
        "texture_accent": "texture",
    }[role]


def _role_orientation(
    role: StyleRole,
    orientation: OrientationConfig,
) -> OrientationConfig:
    multipliers = {
        "outline_detail": (1.00, 0.48),
        "outline_shadow": (0.72, 0.80),
        "fill_mass": (0.32, 1.20),
        "texture_accent": (0.00, 1.85),
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


def _role_palette(
    role: StyleRole,
    palette: Sequence[str],
    modulation: float,
) -> Sequence[str]:
    if role == "outline_detail":
        return palette[: max(1, (len(palette) + 1) // 2)]
    if role == "outline_shadow":
        return palette[: max(1, len(palette) // 2)]
    if role == "texture_accent" and len(palette) > 1:
        return palette[1:]
    if role == "fill_mass" and len(palette) > 2 and modulation >= 0.66:
        return palette[: max(2, (len(palette) + 1) // 2)]
    return palette


def distribute_organic_glyphs(
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
    style_config: OrganicStyleConfig | None = None,
) -> list[Glyph]:
    """Render outline detail/shadow, organic fill and visible texture deterministically."""
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
    config = style_config or OrganicStyleConfig()
    rng = random.Random(seed)

    pools = build_organic_coordinate_pools(valid_coords, config)
    budgets = split_style_role_budget(glyph_count, config)
    coherences: Mapping[StyleRole, float] = {
        "outline_detail": 0.58,
        "outline_shadow": 0.64,
        "fill_mass": 0.38,
        "texture_accent": 0.70,
    }
    salts: Mapping[StyleRole, int] = {
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

        selected = _sample_organic_coordinates(
            pools[role],
            budget,
            rng,
            config.role_cell_sizes[role],
            config.role_capacities[role],
            seed,
            config.organic_scale,
            salts[role],
            coherences[role],
        )
        role_orientation = _role_orientation(role, orientation)
        layer = _role_layer(role)

        for x, y, depth in selected:
            zone = classify_depth_zone(
                depth,
                distribution.edge_threshold,
                distribution.mid_threshold,
            )
            modulation = organic_modulation(
                int(x),
                int(y),
                seed,
                config.organic_scale,
                salts[role],
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
            role_palette = _role_palette(role, palette, modulation)
            glyphs.append(
                Glyph(
                    id=f"{object_id}_{role}_{index}",
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
                    color=rng.choice(role_palette),
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

    render_order = {
        role: index for index, role in enumerate(STYLE_ROLE_ORDER)
    }
    glyphs.sort(
        key=lambda glyph: (
            render_order.get(glyph.style_role, len(render_order)),
            -glyph.font_size,
            glyph.id,
        )
    )
    return glyphs


def summarize_organic_metrics(
    glyphs: Sequence[Glyph],
) -> dict[str, dict[str, float | int]]:
    """Return per-role statistics used for visual regression reports."""
    role_counts = Counter(glyph.style_role for glyph in glyphs)
    summary: dict[str, dict[str, float | int]] = {}
    for role in STYLE_ROLE_ORDER:
        items = [glyph for glyph in glyphs if glyph.style_role == role]
        summary[role] = {
            "count": role_counts.get(role, 0),
            "mean_font_size": (
                fmean(glyph.font_size for glyph in items) if items else 0.0
            ),
            "mean_opacity": (
                fmean(glyph.opacity for glyph in items) if items else 0.0
            ),
            "mean_orientation_strength": (
                fmean(glyph.orientation_strength for glyph in items)
                if items
                else 0.0
            ),
            "mean_depth": fmean(glyph.depth for glyph in items) if items else 0.0,
        }
    return summary
