from collections import Counter
from statistics import mean

import pytest

from engine.glyph_distribution import DistributionConfig, OrientationConfig
from engine.layered_distribution import (
    LayerConfig,
    build_layer_coordinate_pools,
    distribute_layered_glyphs,
    split_layer_budget,
    summarize_layer_metrics,
)


def _coordinates() -> list[tuple[int, int, float]]:
    coordinates: list[tuple[int, int, float]] = []
    for index in range(160):
        coordinates.append((index, 0, 0.08))
        coordinates.append((index, 20, 0.35))
        coordinates.append((index, 40, 0.78))
    return coordinates


def _render(seed: int = 817392, count: int = 200):
    coordinates = _coordinates()
    field = {(x, y): (35.0, 1.0) for x, y, _ in coordinates}
    return distribute_layered_glyphs(
        object_id="moon",
        valid_coords=coordinates,
        character_sequence=("M", "O", "O", "N"),
        glyph_count=count,
        font_size_range=(8.0, 28.0),
        palette=("#172033", "#344966", "#596773", "#8A795D"),
        seed=seed,
        distribution_config=DistributionConfig(cell_size=1),
        orientation_field=field,
        orientation_config=OrientationConfig(jitter_degrees=0.0),
        layer_config=LayerConfig(
            outline_cell_size=1,
            fill_cell_size=1,
            texture_cell_size=1,
            outline_capacity=1,
            fill_capacity=1,
            texture_capacity=1,
        ),
    )


def test_split_layer_budget_preserves_exact_total() -> None:
    budget = split_layer_budget(
        8000,
        {"outline": 0.35, "fill": 0.50, "texture": 0.15},
    )

    assert budget == {"outline": 2800, "fill": 4000, "texture": 1200}
    assert sum(budget.values()) == 8000


@pytest.mark.parametrize(
    "overrides",
    [
        {"outline_ratio": -0.1},
        {"outline_ratio": 0.0, "fill_ratio": 0.0, "texture_ratio": 0.0},
        {"outline_depth_max": 0.0},
        {"fill_depth_min": 1.0},
        {"texture_depth_min": 1.0},
        {"outline_cell_size": 0},
        {"texture_capacity": 0},
        {"fill_orientation_multiplier": -0.1},
    ],
)
def test_layer_config_rejects_invalid_values(overrides: dict) -> None:
    with pytest.raises(ValueError):
        LayerConfig(**overrides)


def test_coordinate_pools_match_layer_responsibilities() -> None:
    config = LayerConfig(
        outline_depth_max=0.18,
        fill_depth_min=0.05,
        texture_depth_min=0.20,
    )
    pools = build_layer_coordinate_pools(_coordinates(), config)

    assert all(depth <= 0.18 for _, _, depth in pools["outline"])
    assert all(depth >= 0.05 for _, _, depth in pools["fill"])
    assert all(depth >= 0.20 for _, _, depth in pools["texture"])


def test_layered_distribution_uses_requested_budgets() -> None:
    glyphs = _render(count=200)
    counts = Counter(glyph.layer for glyph in glyphs)

    assert counts == {"fill": 100, "outline": 70, "texture": 30}
    assert all(glyph.depth <= 0.18 for glyph in glyphs if glyph.layer == "outline")
    assert all(glyph.depth >= 0.20 for glyph in glyphs if glyph.layer == "texture")


def test_layers_have_distinct_visual_roles() -> None:
    glyphs = _render(count=300)
    by_layer = {
        layer: [glyph for glyph in glyphs if glyph.layer == layer]
        for layer in ("outline", "fill", "texture")
    }

    assert mean(glyph.opacity for glyph in by_layer["outline"]) > mean(
        glyph.opacity for glyph in by_layer["fill"]
    )
    assert mean(glyph.opacity for glyph in by_layer["fill"]) > mean(
        glyph.opacity for glyph in by_layer["texture"]
    )
    assert mean(glyph.font_size for glyph in by_layer["outline"]) < mean(
        glyph.font_size for glyph in by_layer["fill"]
    )
    assert mean(glyph.orientation_strength for glyph in by_layer["outline"]) > mean(
        glyph.orientation_strength for glyph in by_layer["fill"]
    )
    assert mean(glyph.orientation_strength for glyph in by_layer["fill"]) > mean(
        glyph.orientation_strength for glyph in by_layer["texture"]
    )


def test_layered_distribution_is_deterministic() -> None:
    first = [glyph.model_dump() for glyph in _render(seed=17)]
    second = [glyph.model_dump() for glyph in _render(seed=17)]
    different = [glyph.model_dump() for glyph in _render(seed=18)]

    assert first == second
    assert first != different


def test_layer_metrics_are_report_ready() -> None:
    metrics = summarize_layer_metrics(_render(count=100))

    assert metrics["outline"]["count"] == 35
    assert metrics["fill"]["count"] == 50
    assert metrics["texture"]["count"] == 15
    assert metrics["outline"]["mean_opacity"] > metrics["texture"]["mean_opacity"]
