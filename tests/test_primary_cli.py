from pathlib import Path

from render_object_from_mask import _build_configs, build_parser


def _args(*extra: str):
    return build_parser().parse_args(
        ["--word", "MOON", "--mask", str(Path("moon_mask.png")), *extra]
    )


def test_balanced_is_the_primary_renderer() -> None:
    args = _args()
    _, _, _, _, _, balanced = _build_configs(args)

    assert args.layer_mode == "balanced"
    assert balanced.outline_ratio == 0.34
    assert balanced.fill_ratio == 0.56
    assert balanced.texture_ratio == 0.10
    assert balanced.fill_dark_probability == 0.08


def test_historical_modes_keep_their_native_defaults() -> None:
    organic_args = _args("--layer-mode", "organic")
    layered_args = _args("--layer-mode", "layered")

    _, _, _, layered_from_organic, organic, _ = _build_configs(organic_args)
    _, _, _, layered, organic_from_layered, _ = _build_configs(layered_args)

    assert organic.fill_ratio == 0.54
    assert organic.texture_ratio == 0.12
    assert layered.fill_ratio == 0.50
    assert layered.texture_ratio == 0.15

    # Building every configuration must not leak one mode's defaults into another.
    assert layered_from_organic.fill_ratio == 0.50
    assert organic_from_layered.fill_ratio == 0.54


def test_explicit_shared_overrides_apply_to_all_modern_modes() -> None:
    args = _args(
        "--outline-ratio",
        "0.30",
        "--fill-ratio",
        "0.60",
        "--texture-ratio",
        "0.10",
    )
    _, _, _, layered, organic, balanced = _build_configs(args)

    for config in (layered, organic, balanced):
        assert config.outline_ratio == 0.30
        assert config.fill_ratio == 0.60
        assert config.texture_ratio == 0.10
