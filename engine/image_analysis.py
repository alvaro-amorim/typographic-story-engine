from __future__ import annotations

from pathlib import Path
from typing import TypeAlias

import numpy as np
from PIL import Image, UnidentifiedImageError
from scipy.ndimage import distance_transform_edt

ValidCoordinate: TypeAlias = tuple[int, int, float]


def get_valid_coordinates(
    mask_path: str,
    threshold: int = 128,
) -> tuple[list[ValidCoordinate], int, int]:
    """Read a mask and return foreground coordinates with normalized depth.

    Dark pixels below ``threshold`` are treated as foreground. The depth value
    is the exact Euclidean distance to the nearest background pixel, normalized
    to the interval 0..1. SciPy is intentionally used here because the exact
    distance transform gives better edge and center measurements than the
    approximate fallback considered during troubleshooting.
    """
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be between 0 and 255")

    path = Path(mask_path)
    if not path.is_file():
        raise FileNotFoundError(f"Mask file not found: {mask_path}")

    try:
        with Image.open(path) as image:
            grayscale = image.convert("L")
            width, height = grayscale.size
            data = np.asarray(grayscale)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError(f"Unable to read mask image: {mask_path}") from exc

    binary_mask = data < threshold
    if not np.any(binary_mask):
        raise ValueError(f"Mask contains no pixels below threshold {threshold}: {mask_path}")

    distance_map = distance_transform_edt(binary_mask)
    max_distance = float(distance_map.max())
    normalized_distance_map = distance_map / max_distance

    y_coords, x_coords = np.where(binary_mask)
    valid_coordinates = [
        (int(x), int(y), float(normalized_distance_map[y, x]))
        for x, y in zip(x_coords, y_coords, strict=True)
    ]

    return valid_coordinates, width, height
