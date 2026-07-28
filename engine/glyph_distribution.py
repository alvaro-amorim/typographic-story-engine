from __future__ import annotations

import random
from collections.abc import Sequence
from typing import List, Tuple

from engine.models import Glyph

ValidCoordinate = Tuple[int, int, float]


def distribute_glyphs(
    object_id: str,
    valid_coords: Sequence[ValidCoordinate],
    character_sequence: Sequence[str],
    glyph_count: int,
    font_size_range: Tuple[float, float],
    palette: Sequence[str],
    seed: int = 42,
    rotation_range: Tuple[float, float] = (-12.0, 12.0),
) -> List[Glyph]:
    """Create deterministic glyphs without mutating Python's global RNG state."""
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

    rng = random.Random(seed)
    glyphs: List[Glyph] = []

    for index in range(glyph_count):
        x, y, distance = rng.choice(valid_coords)
        character = rng.choice(character_sequence)

        normalized_distance = max(0.0, min(1.0, float(distance)))
        base_size = min_size + (max_size - min_size) * normalized_distance
        variance = base_size * 0.20
        final_size = rng.uniform(base_size - variance, base_size + variance)
        final_size = max(min_size, min(max_size, final_size))

        opacity = 1.0 - (0.40 * normalized_distance)

        glyphs.append(
            Glyph(
                id=f"{object_id}_glyph_{index}",
                object_id=object_id,
                character=character,
                x=float(x),
                y=float(y),
                rotation=rng.uniform(min_rotation, max_rotation),
                font_size=float(final_size),
                opacity=float(opacity),
                color=rng.choice(palette),
            )
        )

    # Larger glyphs are rendered first; smaller glyphs retain edge/detail visibility.
    glyphs.sort(key=lambda glyph: glyph.font_size, reverse=True)
    return glyphs
