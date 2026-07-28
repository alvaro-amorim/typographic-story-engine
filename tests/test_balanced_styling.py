from collections import Counter
from statistics import mean

import pytest

from engine.balanced_styling import (
    BalancedStyleConfig,
    build_balanced_coordinate_pools,
    distribute_balanced_glyphs,
    split_balanced_role_budget,
    summarize_balanced_metrics,
)
from engine.glyph_distribution import DistributionConfig, OrientationConfig


def _coordinates() -> list[tuple[int, int, float]]:
    coordinates: list[tuple[int, int, float]] = []
    for y, depth in ((0, 0.05), (20, 0.12), (40, 0.36), (60, 0.78)):
        for x in range(240):
            coordinates.append((x, y, depth))
    return coordinates


def _render(seed: int = 817392, count: int = 400):
    coordinates = _coordinates()
    field = {(x, y): (35.0, 1.0) for x, y, _ in coordinates}
    return distribute_balanced_glyphs(
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
        style_config=BalancedStyleConfig(
            detail_cell_size=1,
            shadow_cell_size=1,
            fill_cell_size=1,
            texture_cell_size=1,
            detail_capacity=1,
            shadow_capacity=1,
            fill_capacity=1,
            texture_capacity=1,
        ),
    )


def test_balanced_budget_preserves_total() -> None:
    budget = split_balanced_role_budget(8000, BalancedStyleConfig())

    assert budget == {
        "outline_shadow": 707,
        "outline_detail": 2013,
        "fill_mass": 4480,
        "texture_accent": 800,
    }
    assert sum(budget.values()) == 8000


@pytest.mark.parametrize(
    "overrides",
    [
        {"fill_ratio": -0.1},
        {"outline_ratio": 0.0, "fill_ratio": 0.0, "texture_ratio": 0.0},
        {"outline_shadow_fraction": 1.2},
        {"outline_detail_depth_max": 0.0},
        {"fill_modulation_strength": 1.2},
        {"fill_dark_probability": -0.1},
        {"fill_opacity_min": 0.8, "fill_opacity_max": 0.5},
        {"metric_cell_size": 0},
    ],
)
def test_balanced_config_rejects_invalid_values(overrides: dict) -> None:
    with pytest.raises(ValueError):
        BalancedStyleConfig(**overrides)


def test_coordinate_pools_preserve_visual_roles() -> None:
    config = BalancedStyleConfig()
    pools = build_balanced_coordinate_pools(_coordinates(), config)

    assert all(depth <= config.outline_detail_depth_max for _, _, depth in pools["outline_detail"])
    assert all(
        config.outline_shadow_depth_min <= depth <= config.outline_depth_max
        for _, _, depth in pools["outline_shadow"]
    )
    assert all(depth >= config.fill_depth_min for _, _, depth in pools["fill_mass"])
    assert all(depth >= config.texture_depth_min for _, _, depth in pools["texture_accent"])


def test_balanced_distribution_is_deterministic() -> None:
    first = [glyph.model_dump() for glyph in _render(seed=17)]
    second = [glyph.model_dump() for glyph in _render(seed=17)]
    different = [glyph.model_dump() for glyph in _render(seed=18)]

    assert first == second
    assert first != different


def test_fill_uses_unique_positions_when_pool_is_large_enough() -> None:
    fill = [glyph for glyph in _render(count=400) if glyph.style_role == "fill_mass"]
    positions = {(glyph.x, glyph.y) for glyph in fill}

    assert len(positions) == len(fill)


def test_fill_has_controlled_contrast_and_limited_dark_color() -> None:
    fill = [glyph for glyph in _render(count=1000) if glyph.style_role == "fill_mass"]
    dark_count = sum(glyph.color == "#172033" for glyph in fill)

    assert dark_count / len(fill) < 0.15
    assert min(glyph.opacity for glyph in fill) >= 0.38
    assert max(glyph.opacity for glyph in fill) <= 0.62


def test_visual_hierarchy_keeps_outline_strong_and_texture_subtle() -> None:
    glyphs = _render(count=800)
    by_role = {
        role: [glyph for glyph in glyphs if glyph.style_role == role]
        for role in (
            "outline_detail",
            "outline_shadow",
            "fill_mass",
            "texture_accent",
        )
    }

    assert mean(glyph.opacity for glyph in by_role["outline_detail"]) > mean(
        glyph.opacity for glyph in by_role["fill_mass"]
    )
    assert mean(glyph.opacity for glyph in by_role["fill_mass"]) > mean(
        glyph.opacity for glyph in by_role["texture_accent"]
    )
    assert mean(glyph.orientation_strength for glyph in by_role["outline_detail"]) > mean(
        glyph.orientation_strength for glyph in by_role["fill_mass"]
    )


def test_metrics_report_local_concentration() -> None:
    glyphs = _render(count=400)
    metrics = summarize_balanced_metrics(glyphs, metric_cell_size=32)

    assert metrics["fill_mass"]["count"] == 224
    assert metrics["fill_mass"]["max_glyphs_per_metric_cell"] > 0
    assert metrics["outline_detail"]["mean_opacity"] > metrics["texture_accent"]["mean_opacity"]


def test_character_frequency_preserves_repeated_o() -> None:
    glyphs = _render(count=4000)
    counts = Counter(glyph.character for glyph in glyphs)

    assert counts["O"] > counts["M"]
    assert counts["O"] > counts["N"]
