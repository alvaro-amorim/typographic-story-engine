from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

import numpy as np
from PIL import Image, UnidentifiedImageError
from scipy.ndimage import distance_transform_edt, gaussian_filter

ValidCoordinate: TypeAlias = tuple[int, int, float]
OrientationSample: TypeAlias = tuple[float, float]


@dataclass(frozen=True)
class MaskAnalysis:
    """Structural data extracted from a raster mask."""

    valid_coordinates: list[ValidCoordinate]
    tangent_field: dict[tuple[int, int], OrientationSample]
    width: int
    height: int


def normalize_axis_angle(angle: float) -> float:
    """Normalize a text-axis angle to the equivalent range [-90, 90)."""
    return ((float(angle) + 90.0) % 180.0) - 90.0


def _safe_gradient(values: np.ndarray, axis: int) -> np.ndarray:
    """Return a zero gradient when an image axis contains a single pixel."""
    if values.shape[axis] < 2:
        return np.zeros_like(values, dtype=float)
    return np.gradient(values, axis=axis)


def compute_tangent_field(
    distance_map: np.ndarray,
    binary_mask: np.ndarray,
    smoothing_sigma: float = 1.25,
) -> dict[tuple[int, int], OrientationSample]:
    """Estimate local tangent direction and confidence for every mask pixel.

    The gradient of the distance transform points approximately along the local
    surface normal. Rotating that vector by 90 degrees produces the tangent used
    to align glyphs with the object's curvature. Gradient magnitude is converted
    into a 0..1 confidence value so unstable medial-axis regions can fall back to
    weaker orientation.
    """
    if distance_map.shape != binary_mask.shape:
        raise ValueError("distance_map and binary_mask must have the same shape")
    if smoothing_sigma < 0.0:
        raise ValueError("smoothing_sigma cannot be negative")
    if distance_map.ndim != 2:
        raise ValueError("distance_map must be a two-dimensional array")

    mask = np.asarray(binary_mask, dtype=bool)
    if not np.any(mask):
        return {}

    smoothed = (
        gaussian_filter(distance_map.astype(float), sigma=smoothing_sigma)
        if smoothing_sigma > 0.0
        else distance_map.astype(float)
    )
    gradient_y = _safe_gradient(smoothed, axis=0)
    gradient_x = _safe_gradient(smoothed, axis=1)
    magnitude = np.hypot(gradient_x, gradient_y)

    foreground_magnitude = magnitude[mask]
    confidence_scale = float(np.percentile(foreground_magnitude, 90))
    if not math.isfinite(confidence_scale) or confidence_scale <= 1e-12:
        confidence_scale = 1.0

    normal_angles = np.degrees(np.arctan2(gradient_y, gradient_x))
    tangent_angles = normal_angles + 90.0
    confidence = np.clip(magnitude / confidence_scale, 0.0, 1.0)

    y_coords, x_coords = np.where(mask)
    return {
        (int(x), int(y)): (
            normalize_axis_angle(float(tangent_angles[y, x])),
            float(confidence[y, x]),
        )
        for x, y in zip(x_coords, y_coords, strict=True)
    }


def analyze_mask(
    mask_path: str,
    threshold: int = 128,
    orientation_smoothing: float = 1.25,
) -> MaskAnalysis:
    """Read a mask and return depth plus curvature information.

    Dark pixels below ``threshold`` are treated as foreground. Depth is the
    exact Euclidean distance to the nearest background pixel, normalized to
    0..1. The tangent field is derived from a smoothed copy of that distance map.
    """
    if not 0 <= threshold <= 255:
        raise ValueError("threshold must be between 0 and 255")
    if orientation_smoothing < 0.0:
        raise ValueError("orientation_smoothing cannot be negative")

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
        raise ValueError(
            f"Mask contains no pixels below threshold {threshold}: {mask_path}"
        )

    distance_map = distance_transform_edt(binary_mask)
    max_distance = float(distance_map.max())
    normalized_distance_map = distance_map / max_distance

    y_coords, x_coords = np.where(binary_mask)
    valid_coordinates = [
        (int(x), int(y), float(normalized_distance_map[y, x]))
        for x, y in zip(x_coords, y_coords, strict=True)
    ]
    tangent_field = compute_tangent_field(
        distance_map,
        binary_mask,
        smoothing_sigma=orientation_smoothing,
    )

    return MaskAnalysis(
        valid_coordinates=valid_coordinates,
        tangent_field=tangent_field,
        width=width,
        height=height,
    )


def get_valid_coordinates(
    mask_path: str,
    threshold: int = 128,
) -> tuple[list[ValidCoordinate], int, int]:
    """Backward-compatible wrapper returning only coordinates and dimensions."""
    analysis = analyze_mask(mask_path, threshold=threshold)
    return analysis.valid_coordinates, analysis.width, analysis.height
