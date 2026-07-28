from statistics import mean

import pytest

from engine.glyph_distribution import (
    DistributionConfig,
    OrientationConfig,
    compute_adaptive_orientation_strength,
    distribute_glyphs,
)


def test_adaptive_strength_is_strongest_at_edge_and_weakest_in_core() -> None:
    distribution = DistributionConfig()
    orientation = OrientationConfig()

    edge = compute_adaptive_orientation_strength(
        "edge", 0.08, 1.0, distribution, orientation
    )
    middle = compute_adaptive_orientation_strength(
        "mid", 0.35, 1.0, distribution, orientation
    )
    core = compute_adaptive_orientation_strength(
        "core", 0.75, 1.0, distribution, orientation
    )

    assert edge > middle > core
    assert edge > 0.75
    assert core < 0.10


def test_deep_core_is_suppressed_more_than_shallow_core() -> None:
    distribution = DistributionConfig()
    orientation = OrientationConfig()

    shallow = compute_adaptive_orientation_strength(
        "core", 0.56, 1.0, distribution, orientation
    )
    deep = compute_adaptive_orientation_strength(
        "core", 0.98, 1.0, distribution, orientation
    )

    assert shallow > deep
    assert deep < shallow * 0.20


def test_core_requires_more_confidence_than_edge() -> None:
    distribution = DistributionConfig()
    orientation = OrientationConfig(min_confidence=0.14)

    edge = compute_adaptive_orientation_strength(
        "edge", 0.08, 0.20, distribution, orientation
    )
    core = compute_adaptive_orientation_strength(
        "core", 0.75, 0.20, distribution, orientation
    )

    assert edge > 0.0
    assert core == 0.0


def test_zone_jitter_increases_toward_core() -> None:
    orientation = OrientationConfig(jitter_degrees=10.0)

    assert orientation.zone_jitters["edge"] == pytest.approx(6.0)
    assert orientation.zone_jitters["mid"] == pytest.approx(10.0)
    assert orientation.zone_jitters["core"] == pytest.approx(16.5)


def test_distribution_records_effective_strength_and_random_core_fallback() -> None:
    valid_coords = (
        [(index, 0, 0.10) for index in range(100)]
        + [(index, 10, 0.40) for index in range(100)]
        + [(index, 20, 0.90) for index in range(100)]
    )
    orientation_field = {
        (x, y): (45.0, 0.18 if y == 20 else 1.0)
        for x, y, _ in valid_coords
    }

    glyphs = distribute_glyphs(
        object_id="adaptive",
        valid_coords=valid_coords,
        character_sequence=tuple("CURVE"),
        glyph_count=150,
        font_size_range=(6.0, 18.0),
        palette=("#111111",),
        seed=817392,
        distribution_config=DistributionConfig(
            edge_ratio=1.0,
            mid_ratio=1.0,
            core_ratio=1.0,
            cell_size=1,
            edge_capacity=1,
            mid_capacity=1,
            core_capacity=1,
        ),
        orientation_field=orientation_field,
        orientation_config=OrientationConfig(),
    )

    by_zone = {
        zone: [glyph for glyph in glyphs if glyph.zone == zone]
        for zone in ("edge", "mid", "core")
    }

    assert all(glyph.orientation_strength > 0.0 for glyph in by_zone["edge"])
    assert mean(glyph.orientation_strength for glyph in by_zone["edge"]) > mean(
        glyph.orientation_strength for glyph in by_zone["mid"]
    )
    assert all(glyph.orientation_source == "random" for glyph in by_zone["core"])
    assert all(glyph.orientation_strength == 0.0 for glyph in by_zone["core"])


def test_adaptive_orientation_remains_deterministic() -> None:
    valid_coords = [
        (x, y, min(1.0, (x + y + 1) / 30.0))
        for y in range(10)
        for x in range(10)
    ]
    orientation_field = {
        (x, y): ((x * 7.0 + y * 3.0) % 180.0 - 90.0, 0.8)
        for x, y, _ in valid_coords
    }
    arguments = {
        "object_id": "adaptive-deterministic",
        "valid_coords": valid_coords,
        "character_sequence": tuple("CURVE"),
        "glyph_count": 80,
        "font_size_range": (6.0, 18.0),
        "palette": ("#111111", "#EEEEEE"),
        "seed": 817392,
        "orientation_field": orientation_field,
        "orientation_config": OrientationConfig(),
    }

    first = [glyph.model_dump() for glyph in distribute_glyphs(**arguments)]
    second = [glyph.model_dump() for glyph in distribute_glyphs(**arguments)]

    assert first == second


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_confidence": 1.0},
        {"confidence_power": 0.0},
        {"jitter_degrees": -1.0},
        {"core_strength": 1.1},
    ],
)
def test_adaptive_orientation_config_rejects_invalid_values(overrides: dict) -> None:
    with pytest.raises(ValueError):
        OrientationConfig(**overrides)
