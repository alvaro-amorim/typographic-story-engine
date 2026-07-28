import random
from collections import Counter

import pytest
from pydantic import ValidationError

from engine.glyph_distribution import distribute_glyphs
from engine.models import Glyph, SemanticObject

VALID_COORDS = [
    (10, 10, 0.0),
    (20, 20, 0.5),
    (30, 30, 1.0),
]


def render(seed: int = 123, count: int = 200):
    return distribute_glyphs(
        object_id="moon_01",
        valid_coords=VALID_COORDS,
        character_sequence=("M", "O", "O", "N"),
        glyph_count=count,
        font_size_range=(8, 28),
        palette=("#111111", "#EEEEEE"),
        seed=seed,
    )


def test_character_sequence_preserves_order_and_repeated_letters() -> None:
    semantic_object = SemanticObject(
        id="moon_01",
        word=" moon ",
        mask_path="moon.png",
    )

    assert semantic_object.word == "MOON"
    assert semantic_object.character_sequence == ("M", "O", "O", "N")
    assert semantic_object.allowed_characters == {"M", "O", "N"}


def test_palette_uses_independent_default_lists() -> None:
    first = SemanticObject(id="a", word="CAT", mask_path="a.png")
    second = SemanticObject(id="b", word="DOG", mask_path="b.png")

    first.palette.append("#FFFFFF")

    assert second.palette == ["#000000"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("word", "123 -"),
        ("glyph_count", 0),
        ("font_size_range", (20, 5)),
        ("overlap", 1.5),
        ("palette", ["black"]),
    ],
)
def test_semantic_object_rejects_invalid_configuration(field: str, value: object) -> None:
    payload = {"id": "cat_01", "word": "CAT", "mask_path": "cat.png"}
    payload[field] = value

    with pytest.raises(ValidationError):
        SemanticObject(**payload)


def test_glyph_normalizes_character_and_color() -> None:
    glyph = Glyph(
        id="g1",
        object_id="cat_01",
        character="c",
        x=10,
        y=20,
        font_size=12,
        color="#aabbcc",
    )

    assert glyph.character == "C"
    assert glyph.color == "#AABBCC"
    assert glyph.zone == "mid"
    assert glyph.depth == 0.0


def test_same_seed_generates_identical_glyphs() -> None:
    first = [glyph.model_dump() for glyph in render(seed=817392)]
    second = [glyph.model_dump() for glyph in render(seed=817392)]

    assert first == second


def test_different_seed_changes_the_scene() -> None:
    first = [glyph.model_dump() for glyph in render(seed=1)]
    second = [glyph.model_dump() for glyph in render(seed=2)]

    assert first != second


def test_distribution_does_not_mutate_global_random_state() -> None:
    random.seed(999)
    expected_first = random.random()
    expected_second = random.random()

    random.seed(999)
    actual_first = random.random()
    render(seed=42, count=10)
    actual_second = random.random()

    assert actual_first == expected_first
    assert actual_second == expected_second


def test_repeated_word_letters_preserve_sampling_weight() -> None:
    glyphs = render(seed=77, count=8000)
    counts = Counter(glyph.character for glyph in glyphs)

    assert counts["O"] > counts["M"]
    assert counts["O"] > counts["N"]
    assert 0.45 <= counts["O"] / len(glyphs) <= 0.55


def test_generated_values_stay_inside_configured_ranges() -> None:
    glyphs = render()

    assert all(8 <= glyph.font_size <= 28 for glyph in glyphs)
    assert all(0.38 <= glyph.opacity <= 1.0 for glyph in glyphs)
    assert all(-12 <= glyph.rotation <= 12 for glyph in glyphs)
    assert all(glyph.character in {"M", "O", "N"} for glyph in glyphs)
    assert all(glyph.zone in {"edge", "mid", "core"} for glyph in glyphs)
    assert all(0.0 <= glyph.depth <= 1.0 for glyph in glyphs)


@pytest.mark.parametrize(
    "overrides",
    [
        {"valid_coords": []},
        {"character_sequence": []},
        {"palette": []},
        {"glyph_count": 0},
        {"font_size_range": (20, 5)},
        {"rotation_range": (10, -10)},
    ],
)
def test_invalid_distribution_inputs_raise_clear_errors(overrides: dict) -> None:
    arguments = {
        "object_id": "cat_01",
        "valid_coords": VALID_COORDS,
        "character_sequence": ("C", "A", "T"),
        "glyph_count": 10,
        "font_size_range": (8, 28),
        "palette": ("#000000",),
        "seed": 42,
    }
    arguments.update(overrides)

    with pytest.raises(ValueError):
        distribute_glyphs(**arguments)
