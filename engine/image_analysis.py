from __future__ import annotations

import math
from pathlib import Path
from typing import TypeAlias

import numpy as np
from PIL import Image, UnidentifiedImageError

ValidCoordinate: TypeAlias = tuple[int, int, float]


def _chamfer_distance_transform(binary_mask: np.ndarray) -> np.ndarray:
    """Approximate the distance from each foreground pixel to the background.

    The implementation uses a deterministic two-pass 8-neighbour chamfer
    transform. It is intentionally implemented with NumPy only so the core
    renderer does not depend on SciPy or native scientific libraries.

    Pixels outside the canvas are treated as background by padding the mask
    before the two passes. This keeps objects that touch the canvas border
    correctly normalized.
    """
    if binary_mask.ndim != 2:
        raise ValueError("binary_mask must be a two-dimensional array")

    padded_mask = np.pad(
        binary_mask.astype(bool, copy=False),
        pad_width=1,
        mode="constant",
        constant_values=False,
    )
    height, width = padded_mask.shape
    unreachable = float(height + width)
    diagonal_cost = math.sqrt(2.0)

    distances = np.where(padded_mask, unreachable, 0.0).astype(
        np.float32,
        copy=False,
    )

    # Forward pass: inspect neighbours that have already been processed.
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if not padded_mask[y, x]:
                continue

            distances[y, x] = min(
                distances[y, x],
                distances[y - 1, x] + 1.0,
                distances[y, x - 1] + 1.0,
                distances[y - 1, x - 1] + diagonal_cost,
                distances[y - 1, x + 1] + diagonal_cost,
            )

    # Backward pass: complete the propagation from the opposite direction.
    for y in range(height - 2, 0, -1):
        for x in range(width - 2, 0, -1):
            if not padded_mask[y, x]:
                continue

            distances[y, x] = min(
                distances[y, x],
                distances[y + 1, x] + 1.0,
                distances[y, x + 1] + 1.0,
                distances[y + 1, x + 1] + diagonal_cost,
                distances[y + 1, x - 1] + diagonal_cost,
            )

    return distances[1:-1, 1:-1]


def get_valid_coordinates(
    mask_path: str,
    threshold: int = 128,
) -> tuple[list[ValidCoordinate], int, int]:
    """Read a mask and return valid pixels with normalized edge distance.

    Dark pixels below ``threshold`` are considered part of the semantic
    object. Each returned tuple contains ``(x, y, normalized_distance)`` where
    the distance is 0 near the contour and approaches 1 in the deepest part of
    the object.
    """
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be between 0 and 255")

    path = Path(mask_path)
    if not path.is_file():
        raise FileNotFoundError(f"Mask file not found: {path}")

    try:
        with Image.open(path) as source:
            image = source.convert("L")
            width, height = image.size
            data = np.asarray(image, dtype=np.uint8)
    except UnidentifiedImageError as exc:
        raise ValueError(f"Mask file is not a readable image: {path}") from exc

    binary_mask = data < threshold
    if not bool(binary_mask.any()):
        raise ValueError(
            f"Mask '{path}' contains no pixels darker than threshold {threshold}"
        )

    distance_map = _chamfer_distance_transform(binary_mask)
    max_distance = float(distance_map.max())

    if max_distance > 0:
        normalized_distance_map = distance_map / max_distance
    else:
        normalized_distance_map = distance_map

    y_coordinates, x_coordinates = np.where(binary_mask)
    valid_coordinates = [
        (
            int(x),
            int(y),
            float(normalized_distance_map[y, x]),
        )
        for x, y in zip(x_coordinates, y_coordinates, strict=True)
    ]

    return valid_coordinates, width, height
