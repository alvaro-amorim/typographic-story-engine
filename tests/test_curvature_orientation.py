import numpy as np
import pytest

from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    blend_axis_angles,
    distribute_glyphs,
)
from engine.image_analysis import compute_tangent_field


def test_tangent_field_follows_rectangle_edges() -> None:
    mask = np.zeros((25, 25), dtype=bool)
    mask[4:21, 4:21] = True

    from scipy.ndimage import distance_transform_edt

    distance_map = distance_transform_edt(mask)
    field = compute_tangent_field(
        distance_map,
        mask,
        smoothing_sigma=0.8,
    )

    top_angle, top_confidence = field[(12, 4)]
    left_angle, left_confidence = field[(4, 12)]

    assert abs(top_angle) < 12.0
    assert abs(abs(left_angle) - 90.0) < 12.0
    assert top_confidence > 0.5
    assert left_confidence > 0.5


def test_axis_angle_blend_handles_180_degree_equivalence() -> None:
    blended = blend_axis_angles(
        random_angle=88.0,
        tangent_angle=-88.0,
        tangent_strength=0.5,
    )

    assert abs(abs(blended) - 90.0) < 3.0


def test_full_tangent_strength_matches_orientation_field() -> None:
    valid_coords = [(x, 0, 0.1) for x in range(20)]
    orientation_field = {(x, 0): (45.0, 1.0) for x in range(20)}
    distribution = DistributionConfig(
        edge_ratio=1.0,
        mid_ratio=0.0,
        core_ratio=0.0,
        cell_size=1,
        edge_capacity=1,
    )
    orientation = OrientationConfig(
        edge_strength=1.0,
        mid_strength=1.0,
        core_strength=1.0,
        jitter_degrees=0.0,
        min_confidence=0.0,
    )

    glyphs = distribute_glyphs(
        object_id="curve",
        valid_coords=valid_coords,
        character_sequence=("C",),
        glyph_count=20,
        font_size_range=(8.0, 12.0),
        palette=("#000000",),
        seed=7,
        rotation_range=(0.0, 0.0),
        distribution_config=distribution,
        orientation_field=orientation_field,
        orientation_config=orientation,
    )

    assert all(glyph.rotation == pytest.approx(45.0) for glyph in glyphs)
    assert all(glyph.orientation_angle == pytest.approx(45.0) for glyph in glyphs)
    assert all(
        glyph.orientation_confidence == pytest.approx(1.0)
        for glyph in glyphs
    )
    assert all(glyph.orientation_source == "tangent" for glyph in glyphs)


def test_low_confidence_falls_back_to_random_rotation() -> None:
    valid_coords = [(0, 0, 0.1)]
    orientation_field = {(0, 0): (75.0, 0.02)}
    orientation = OrientationConfig(
        min_confidence=0.1,
        jitter_degrees=0.0,
    )

    glyph = distribute_glyphs(
        object_id="fallback",
        valid_coords=valid_coords,
        character_sequence=("F",),
        glyph_count=1,
        font_size_range=(8.0, 12.0),
        palette=("#000000",),
        seed=4,
        rotation_range=(-5.0, 5.0),
        orientation_field=orientation_field,
        orientation_config=orientation,
    )[0]

    assert -5.0 <= glyph.rotation <= 5.0
    assert glyph.orientation_angle == pytest.approx(75.0)
    assert glyph.orientation_confidence == pytest.approx(0.02)
    assert glyph.orientation_source == "random"


def test_curvature_distribution_is_deterministic() -> None:
    valid_coords = [
        (x, y, min(1.0, (x + y + 1) / 30.0))
        for y in range(10)
        for x in range(10)
    ]
    orientation_field = {
        (x, y): ((x * 7.0 + y * 3.0) % 180.0 - 90.0, 0.8)
        for x, y, _ in valid_coords
    }

    first = distribute_glyphs(
        object_id="deterministic",
        valid_coords=valid_coords,
        character_sequence=tuple("CURVE"),
        glyph_count=80,
        font_size_range=(6.0, 18.0),
        palette=("#111111", "#EEEEEE"),
        seed=817392,
        orientation_field=orientation_field,
    )
    second = distribute_glyphs(
        object_id="deterministic",
        valid_coords=valid_coords,
        character_sequence=tuple("CURVE"),
        glyph_count=80,
        font_size_range=(6.0, 18.0),
        palette=("#111111", "#EEEEEE"),
        seed=817392,
        orientation_field=orientation_field,
    )

    assert [glyph.model_dump() for glyph in first] == [
        glyph.model_dump() for glyph in second
    ]


def test_orientation_config_validation() -> None:
    with pytest.raises(ValueError, match="between zero and one"):
        OrientationConfig(edge_strength=1.1)

    with pytest.raises(ValueError, match="cannot be negative"):
        OrientationConfig(jitter_degrees=-1.0)
