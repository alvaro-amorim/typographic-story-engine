from __future__ import annotations

import math
import random
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
from engine.models import Glyph

LayerName = Literal["outline", "fill", "texture"]
LAYER_NAMES: tuple[LayerName, ...] = ("outline", "fill", "texture")


@dataclass(frozen=True)
class LayerConfig:
    """Controls independent structural, mass and texture glyph layers."""

    enabled: bool = True
    outline_ratio: float = 0.35
    fill_ratio: float = 0.50
    texture_ratio: float = 0.15
    outline_depth_max: float = 0.18
    fill_depth_min: float = 0.035
    texture_depth_min: float = 0.20
    outline_cell_size: int = 5
    fill_cell_size: int = 9
    texture_cell_size: int = 14
    outline_capacity: int = 3
    fill_capacity: int = 2
    texture_capacity: int = 1
    outline_orientation_multiplier: float = 1.0
    fill_orientation_multiplier: float = 0.45
    texture_orientation_multiplier: float = 0.08
    outline_jitter_multiplier: float = 0.60
    fill_jitter_multiplier: float = 1.0
    texture_jitter_multiplier: float = 1.55

    def __post_init__(self) -> None:
        ratios = self.layer_ratios
        if any(ratio < 0.0 for ratio in ratios.values()):
            raise ValueError("layer ratios cannot be negative")
        if math.isclose(sum(ratios.values()), 0.0):
            raise ValueError("at least one layer ratio must be greater than zero")

        if not 0.0 < self.outline_depth_max < 1.0:
            raise ValueError("outline_depth_max must be between zero and one")
        if not 0.0 <= self.fill_depth_min < 1.0:
            raise ValueError("fill_depth_min must be between zero inclusive and one exclusive")
        if not 0.0 <= self.texture_depth_min < 1.0:
            raise ValueError("texture_depth_min must be between zero inclusive and one exclusive")

        if any(size <= 0 for size in self.layer_cell_sizes.values()):
            raise ValueError("layer cell sizes must be greater than zero")
        if any(capacity <= 0 for capacity in self.layer_capacities.values()):
            raise ValueError("layer capacities must be greater than zero")
        if any(multiplier < 0.0 for multiplier in self.orientation_multipliers.values()):
            raise ValueError("orientation multipliers cannot be negative")
        if any(multiplier < 0.0 for multiplier in self.jitter_multipliers.values()):
            raise ValueError("jitter multipliers cannot be negative")

    @property
    def layer_ratios(self) -> dict[LayerName, float]:
        return {
            "outline": self.outline_ratio,
            "fill": self.fill_ratio,
            "texture": self.texture_ratio,
        }

    @property
    def layer_cell_sizes(self) -> dict[LayerName, int]:
        return {
            "outline": self.outline_cell_size,
            "fill": self.fill_cell_size,
            "texture": self.texture_cell_size,
        }

    @property
    def layer_capacities(self) -> dict[LayerName, int]:
        return {
            "outline": self.outline_capacity,
            "fill": self.fill_capacity,
            "texture": self.texture_capacity,
        }

    @property
    def orientation_multipliers(self) -> dict[LayerName, float]:
        return {
            "outline": self.outline_orientation_multiplier,
            "fill": self.fill_orientation_multiplier,
            "texture": self.texture_orientation_multiplier,
        }

    @property
    def jitter_multipliers(self) -> dict[LayerName, float]:
        return {
            "outline": self.outline_jitter_multiplier,
            "fill": self.fill_jitter_multiplier,
            "texture": self.texture_jitter_multiplier,
        }


def split_layer_budget(
    glyph_count: int,
    layer_ratios: Mapping[LayerName, float],
) -> dict[LayerName, int]:
    """Split the glyph total exactly with deterministic largest remainders."""
    if glyph_count <= 0:
        raise ValueError("glyph_count must be greater than zero")

    ratios = {layer: float(layer_ratios.get(layer, 0.0)) for layer in LAYER_NAMES}
    if any(ratio < 0.0 for ratio in ratios.values()):
        raise ValueError("layer ratios cannot be negative")

    total = sum(ratios.values())
    if total <= 0.0:
        raise ValueError("at least one layer ratio must be greater than zero")

    raw = {layer: glyph_count * ratios[layer] / total for layer in LAYER_NAMES}
    budget = {layer: math.floor(raw[layer]) for layer in LAYER_NAMES}
    remaining = glyph_count - sum(budget.values())
    order = sorted(
        LAYER_NAMES,
        key=lambda layer: (raw[layer] - budget[layer], -LAYER_NAMES.index(layer)),
        reverse=True,
    )
    for layer in order[:remaining]:
        budget[layer] += 1
    return budget


def build_layer_coordinate_pools(
    valid_coords: Sequence[ValidCoordinate],
    config: LayerConfig,
) -> dict[LayerName, list[ValidCoordinate]]:
    """Build overlapping pools so each layer can solve a different visual task."""
    if not valid_coords:
        raise ValueError("valid_coords cannot be empty")

    coordinates = [
        (int(x), int(y), max(0.0, min(1.0, float(depth))))
        for x, y, depth in valid_coords
    ]
    outline = [coord for coord in coordinates if coord[2] <= config.outline_depth_max]
    fill = [coord for coord in coordinates if coord[2] >= config.fill_depth_min]
    texture = [coord for coord in coordinates if coord[2] >= config.texture_depth_min]

    if not outline:
        shallowest = min(coord[2] for coord in coordinates)
        outline = [coord for coord in coordinates if coord[2] <= shallowest + 0.05]
    if not fill:
        fill = list(coordinates)
    if not texture:
        deepest = sorted(coordinates, key=lambda coord: coord[2], reverse=True)
        texture = deepest[: max(1, len(deepest) // 4)]

    return {"outline": outline, "fill": fill, "texture": texture}


def _interpolate(start: float, end: float, amount: float) -> float:
    clamped = max(0.0, min(1.0, float(amount)))
    return start + (end - start) * clamped


def _layer_font_size(
    layer: LayerName,
    zone: ZoneName,
    depth: float,
    font_size_range: Tuple[float, float],
    distribution: DistributionConfig,
    layers: LayerConfig,
    rng: random.Random,
) -> float:
    minimum, maximum = font_size_range
    span = maximum - minimum

    if layer == "outline":
        progress = depth / max(layers.outline_depth_max, 1e-12)
        low, high = minimum, minimum + span * 0.29
    elif layer == "texture":
        progress = (depth - layers.texture_depth_min) / max(
            1e-12, 1.0 - layers.texture_depth_min
        )
        low, high = minimum, minimum + span * 0.24
    else:
        if zone == "edge":
            progress = depth / distribution.edge_threshold
            low, high = minimum + span * 0.08, minimum + span * 0.34
        elif zone == "mid":
            progress = (depth - distribution.edge_threshold) / max(
                1e-12, distribution.mid_threshold - distribution.edge_threshold
            )
            low, high = minimum + span * 0.14, minimum + span * 0.58
        else:
            progress = (depth - distribution.mid_threshold) / max(
                1e-12, 1.0 - distribution.mid_threshold
            )
            low, high = minimum + span * 0.22, minimum + span * 0.66

    base = _interpolate(low, high, progress)
    variance_multiplier = {"outline": 0.055, "fill": 0.075, "texture": 0.12}[layer]
    variance = max(0.25, base * variance_multiplier)
    return max(minimum, min(maximum, rng.uniform(base - variance, base + variance)))


def _layer_opacity(
    layer: LayerName,
    zone: ZoneName,
    depth: float,
    distribution: DistributionConfig,
    layers: LayerConfig,
    rng: random.Random,
) -> float:
    if layer == "outline":
        progress = depth / max(layers.outline_depth_max, 1e-12)
        base = _interpolate(0.99, 0.82, progress)
        variance = 0.025
    elif layer == "texture":
        progress = (depth - layers.texture_depth_min) / max(
            1e-12, 1.0 - layers.texture_depth_min
        )
        base = _interpolate(0.23, 0.10, progress)
        variance = 0.025
    else:
        if zone == "edge":
            progress = depth / distribution.edge_threshold
            base = _interpolate(0.76, 0.62, progress)
        elif zone == "mid":
            progress = (depth - distribution.edge_threshold) / max(
                1e-12, distribution.mid_threshold - distribution.edge_threshold
            )
            base = _interpolate(0.63, 0.47, progress)
        else:
            progress = (depth - distribution.mid_threshold) / max(
                1e-12, 1.0 - distribution.mid_threshold
            )
            base = _interpolate(0.49, 0.34, progress)
        variance = 0.035

    return max(0.0, min(1.0, base + rng.uniform(-variance, variance)))


def _palette_for_layer(
    layer: LayerName,
    palette: Sequence[str],
) -> Sequence[str]:
    if layer == "outline":
        return palette[: max(1, (len(palette) + 1) // 2)]
    if layer == "texture" and len(palette) > 1:
        return palette[1:]
    return palette


def _orientation_for_layer(
    layer: LayerName,
    orientation: OrientationConfig,
    layers: LayerConfig,
) -> OrientationConfig:
    strength = layers.orientation_multipliers[layer]
    jitter = layers.jitter_multipliers[layer]
    return replace(
        orientation,
        edge_strength=min(1.0, orientation.edge_strength * strength),
        mid_strength=min(1.0, orientation.mid_strength * strength),
        core_strength=min(1.0, orientation.core_strength * strength),
        jitter_degrees=orientation.jitter_degrees * jitter,
    )


def distribute_layered_glyphs(
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
    layer_config: LayerConfig | None = None,
) -> list[Glyph]:
    """Create deterministic outline, fill and texture glyph layers."""
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
    layers = layer_config or LayerConfig()
    rng = random.Random(seed)

    pools = build_layer_coordinate_pools(valid_coords, layers)
    budgets = split_layer_budget(glyph_count, layers.layer_ratios)
    glyphs: list[Glyph] = []
    index = 0

    for layer in LAYER_NAMES:
        budget = budgets[layer]
        if budget == 0:
            continue

        selected = sample_zone_coordinates(
            pools[layer],
            budget,
            rng,
            layers.layer_cell_sizes[layer],
            layers.layer_capacities[layer],
        )
        layer_orientation = _orientation_for_layer(layer, orientation, layers)
        layer_palette = _palette_for_layer(layer, palette)

        for x, y, depth in selected:
            zone = classify_depth_zone(
                depth,
                distribution.edge_threshold,
                distribution.mid_threshold,
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
                orientation_config=layer_orientation,
                rng=rng,
            )
            glyphs.append(
                Glyph(
                    id=f"{object_id}_{layer}_{index}",
                    object_id=object_id,
                    character=rng.choice(character_sequence),
                    x=float(x),
                    y=float(y),
                    rotation=float(rotation),
                    font_size=float(
                        _layer_font_size(
                            layer,
                            zone,
                            depth,
                            font_size_range,
                            distribution,
                            layers,
                            rng,
                        )
                    ),
                    opacity=float(
                        _layer_opacity(
                            layer,
                            zone,
                            depth,
                            distribution,
                            layers,
                            rng,
                        )
                    ),
                    color=rng.choice(layer_palette),
                    zone=zone,
                    layer=layer,
                    depth=depth,
                    orientation_angle=orientation_angle,
                    orientation_confidence=orientation_confidence,
                    orientation_strength=orientation_strength,
                    orientation_source=orientation_source,
                )
            )
            index += 1

    render_order = {"texture": 0, "fill": 1, "outline": 2}
    glyphs.sort(
        key=lambda glyph: (
            render_order[glyph.layer],
            -glyph.font_size,
            glyph.id,
        )
    )
    return glyphs


def summarize_layer_metrics(glyphs: Sequence[Glyph]) -> dict[str, dict[str, float | int]]:
    """Return compact per-layer statistics for validation reports and tuning."""
    summary: dict[str, dict[str, float | int]] = {}
    for layer in ("outline", "fill", "texture"):
        items = [glyph for glyph in glyphs if glyph.layer == layer]
        summary[layer] = {
            "count": len(items),
            "mean_font_size": fmean(glyph.font_size for glyph in items) if items else 0.0,
            "mean_opacity": fmean(glyph.opacity for glyph in items) if items else 0.0,
            "mean_orientation_strength": (
                fmean(glyph.orientation_strength for glyph in items) if items else 0.0
            ),
        }
    return summary
