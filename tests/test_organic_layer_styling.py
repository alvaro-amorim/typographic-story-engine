from collections import Counter
from statistics import mean

import pytest

from engine.glyph_distribution import DistributionConfig, OrientationConfig
from engine.organic_styling import (
    OrganicStyleConfig,
    build_organic_coordinate_pools,
    distribute_organic_glyphs,
    organic_modulation,
    split_style_role_budget,
    summarize_organic_metrics,
)


def _coordinates() -> list[tuple[int, int, float]]:
    coordinates: list[tuple[int, int, float]] = []
    depths = (0.05, 0.09, 0.14, 0.35, 0.75)
    for x in range(240):
        for row, depth in enumerate(depths):
            coordinates.append((x, row * 20, depth))
    return coordinates


def _render(seed: int = 817392, count: int = 500):
    coordinates = _coordinates()
    field = {(x, y): (35.0, 1.0) for x, y, _ in coordinates}
    return distribute_organic_glyphs(
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
        style_config=OrganicStyleConfig(
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


def test_style_role_budget_preserves_total_and_outline_split() -> None:
    budget = split_style_role_budget(500, OrganicStyleConfig())

    assert budget == {
        "outline_shadow": 54,
        "outline_detail": 116,
        "fill_mass": 270,
        "texture_accent": 60,
    }
    assert sum(budget.values()) == 500


@pytest.mark.parametrize(
    "overrides",
    [
        {"outline_ratio": -0.1},
        {"outline_ratio": 0.0, "fill_ratio": 0.0, "texture_ratio": 0.0},
        {"outline_shadow_fraction": 1.1},
        {"outline_detail_depth_max": 0.0},
        {"outline_detail_depth_max": 0.2, "outline_depth_max": 0.1},
        {"outline_shadow_depth_min": 0.2, "outline_depth_max": 0.18},
        {"organic_scale": 0.0},
        {"texture_opacity_min": 0.5, "texture_opacity_max": 0.4},
        {"detail_cell_size": 0},
        {"texture_capacity": 0},
    ],
)
def test_organic_config_rejects_invalid_values(overrides: dict) -> None:
    with pytest.raises(ValueError):
        OrganicStyleConfig(**overrides)


def test_coordinate_pools_match_visual_roles() -> None:
    config = OrganicStyleConfig()
    pools = build_organic_coordinate_pools(_coordinates(), config)

    assert all(depth <= config.outline_detail_depth_max for _, _, depth in pools["outline_detail"])
    assert all(
        config.outline_shadow_depth_min <= depth <= config.outline_depth_max
        for _, _, depth in pools["outline_shadow"]
    )
    assert all(depth >= config.fill_depth_min for _, _, depth in pools["fill_mass"])
    assert all(depth >= config.texture_depth_min for _, _, depth in pools["texture_accent"])


def test_organic_modulation_is_stable_bounded_and_spatial() -> None:
    first = organic_modulation(20, 30, seed=17)
    repeated = organic_modulation(20, 30, seed=17)
    moved = organic_modulation(120, 90, seed=17)
    different_seed = organic_modulation(20, 30, seed=18)

    assert 0.0 <= first <= 1.0
    assert first == repeated
    assert first != moved
    assert first != different_seed


def test_organic_distribution_uses_requested_roles() -> None:
    glyphs = _render(count=500)
    counts = Counter(glyph.style_role for glyph in glyphs)

    assert counts == {
        "fill_mass": 270,
        "outline_detail": 116,
        "texture_accent": 60,
        "outline_shadow": 54,
    }
    assert all(glyph.layer == "outline" for glyph in glyphs if glyph.style_role.startswith("outline_"))
    assert all(glyph.layer == "fill" for glyph in glyphs if glyph.style_role == "fill_mass")
    assert all(glyph.layer == "texture" for glyph in glyphs if glyph.style_role == "texture_accent")


def test_roles_have_distinct_art_direction() -> None:
    glyphs = _render(count=800)
    by_role = {
        role: [glyph for glyph in glyphs if glyph.style_role == role]
        for role in (
            "outline_shadow",
            "outline_detail",
            "fill_mass",
            "texture_accent",
        )
    }

    assert mean(glyph.opacity for glyph in by_role["outline_detail"]) > mean(
        glyph.opacity for glyph in by_role["outline_shadow"]
    )
    assert mean(glyph.font_size for glyph in by_role["outline_shadow"]) > mean(
        glyph.font_size for glyph in by_role["outline_detail"]
    )
    assert mean(glyph.opacity for glyph in by_role["fill_mass"]) > mean(
        glyph.opacity for glyph in by_role["texture_accent"]
    )
    assert mean(glyph.opacity for glyph in by_role["texture_accent"]) > 0.20
    assert mean(
        glyph.orientation_strength for glyph in by_role["outline_detail"]
    ) > mean(glyph.orientation_strength for glyph in by_role["outline_shadow"])
    assert mean(
        glyph.orientation_strength for glyph in by_role["outline_shadow"]
    ) > mean(glyph.orientation_strength for glyph in by_role["fill_mass"])
    assert all(
        glyph.orientation_source == "random"
        for glyph in by_role["texture_accent"]
    )


def test_organic_distribution_is_deterministic() -> None:
    first = [glyph.model_dump() for glyph in _render(seed=17)]
    second = [glyph.model_dump() for glyph in _render(seed=17)]
    different = [glyph.model_dump() for glyph in _render(seed=18)]

    assert first == second
    assert first != different


def test_organic_metrics_are_report_ready() -> None:
    metrics = summarize_organic_metrics(_render(count=500))

    assert metrics["outline_shadow"]["count"] == 54
    assert metrics["outline_detail"]["count"] == 116
    assert metrics["fill_mass"]["count"] == 270
    assert metrics["texture_accent"]["count"] == 60
    assert metrics["outline_detail"]["mean_opacity"] > metrics["texture_accent"]["mean_opacity"]
