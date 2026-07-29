from collections import Counter, defaultdict
from statistics import mean

import pytest

from engine.glyph_distribution import (
    DistributionConfig,
    classify_depth_zone,
    distribute_glyphs,
    sample_zone_coordinates,
    split_glyph_budget,
)


def _zone_coordinates() -> list[tuple[int, int, float]]:
    coordinates: list[tuple[int, int, float]] = []
    for index in range(120):
        coordinates.append((index, 0, 0.10))
        coordinates.append((index, 20, 0.40))
        coordinates.append((index, 40, 0.82))
    return coordinates


def test_classify_depth_zone_respects_boundaries() -> None:
    assert classify_depth_zone(0.0, 0.18, 0.55) == "edge"
    assert classify_depth_zone(0.18, 0.18, 0.55) == "edge"
    assert classify_depth_zone(0.19, 0.18, 0.55) == "mid"
    assert classify_depth_zone(0.55, 0.18, 0.55) == "mid"
    assert classify_depth_zone(0.56, 0.18, 0.55) == "core"
    assert classify_depth_zone(1.0, 0.18, 0.55) == "core"


def test_split_glyph_budget_preserves_exact_total() -> None:
    budget = split_glyph_budget(
        8000,
        {"edge": 0.45, "mid": 0.35, "core": 0.20},
    )

    assert budget == {"edge": 3600, "mid": 2800, "core": 1600}
    assert sum(budget.values()) == 8000


def test_split_glyph_budget_handles_rounding_deterministically() -> None:
    budget = split_glyph_budget(
        7,
        {"edge": 1.0, "mid": 1.0, "core": 1.0},
    )

    assert budget == {"edge": 3, "mid": 2, "core": 2}


@pytest.mark.parametrize(
    "overrides",
    [
        {"edge_threshold": 0.0},
        {"edge_threshold": 0.7, "mid_threshold": 0.6},
        {"mid_threshold": 1.0},
        {"edge_ratio": -0.1},
        {"edge_ratio": 0.0, "mid_ratio": 0.0, "core_ratio": 0.0},
        {"cell_size": 0},
        {"core_capacity": 0},
    ],
)
def test_distribution_config_rejects_invalid_values(overrides: dict) -> None:
    with pytest.raises(ValueError):
        DistributionConfig(**overrides)


def test_shape_aware_distribution_uses_requested_zone_budgets() -> None:
    config = DistributionConfig(
        edge_ratio=0.45,
        mid_ratio=0.35,
        core_ratio=0.20,
        cell_size=1,
        edge_capacity=1,
        mid_capacity=1,
        core_capacity=1,
    )

    glyphs = distribute_glyphs(
        object_id="moon_01",
        valid_coords=_zone_coordinates(),
        character_sequence=("M", "O", "O", "N"),
        glyph_count=100,
        font_size_range=(8.0, 28.0),
        palette=("#111111", "#EEEEEE"),
        seed=817392,
        distribution_config=config,
    )

    zone_counts = Counter(glyph.zone for glyph in glyphs)
    assert zone_counts == {"edge": 45, "mid": 35, "core": 20}


def test_edge_is_smaller_and_more_opaque_than_core() -> None:
    glyphs = distribute_glyphs(
        object_id="moon_01",
        valid_coords=_zone_coordinates(),
        character_sequence=("M", "O", "O", "N"),
        glyph_count=300,
        font_size_range=(8.0, 28.0),
        palette=("#111111",),
        seed=42,
        distribution_config=DistributionConfig(cell_size=1),
    )

    by_zone = {
        zone: [glyph for glyph in glyphs if glyph.zone == zone]
        for zone in ("edge", "mid", "core")
    }

    assert mean(glyph.font_size for glyph in by_zone["edge"]) < mean(
        glyph.font_size for glyph in by_zone["mid"]
    )
    assert mean(glyph.font_size for glyph in by_zone["mid"]) < mean(
        glyph.font_size for glyph in by_zone["core"]
    )
    assert mean(glyph.opacity for glyph in by_zone["edge"]) > mean(
        glyph.opacity for glyph in by_zone["mid"]
    )
    assert mean(glyph.opacity for glyph in by_zone["mid"]) > mean(
        glyph.opacity for glyph in by_zone["core"]
    )


def test_spatial_sampler_spreads_glyphs_across_cells() -> None:
    coordinates = [
        (x, y, 0.1)
        for y in range(20)
        for x in range(20)
    ]

    import random

    selected = sample_zone_coordinates(
        coordinates,
        target_count=20,
        rng=random.Random(123),
        cell_size=4,
        capacity=1,
    )

    assert len(selected) == 20
    assert len(set(selected)) == 20

    occupancy: dict[tuple[int, int], int] = defaultdict(int)
    for x, y, _ in selected:
        occupancy[(x // 4, y // 4)] += 1

    assert max(occupancy.values()) == 1


def test_shape_aware_distribution_remains_deterministic() -> None:
    arguments = {
        "object_id": "moon_01",
        "valid_coords": _zone_coordinates(),
        "character_sequence": ("M", "O", "O", "N"),
        "glyph_count": 180,
        "font_size_range": (8.0, 28.0),
        "palette": ("#111111", "#EEEEEE"),
        "seed": 9001,
        "distribution_config": DistributionConfig(cell_size=2),
    }

    first = [glyph.model_dump() for glyph in distribute_glyphs(**arguments)]
    second = [glyph.model_dump() for glyph in distribute_glyphs(**arguments)]

    assert first == second


def test_empty_zone_budget_is_redistributed() -> None:
    coordinates = [
        (index, 0, 0.08) for index in range(100)
    ] + [
        (index, 20, 0.35) for index in range(100)
    ]

    glyphs = distribute_glyphs(
        object_id="thin_01",
        valid_coords=coordinates,
        character_sequence=("T", "H", "I", "N"),
        glyph_count=100,
        font_size_range=(6.0, 18.0),
        palette=("#000000",),
        seed=3,
        distribution_config=DistributionConfig(cell_size=1),
    )

    zone_counts = Counter(glyph.zone for glyph in glyphs)
    assert len(glyphs) == 100
    assert zone_counts["core"] == 0
    assert zone_counts["edge"] + zone_counts["mid"] == 100
