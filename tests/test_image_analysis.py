import pytest
from PIL import Image, ImageDraw

from engine.image_analysis import get_valid_coordinates


def test_get_valid_coordinates_normalizes_mask_depth(tmp_path) -> None:
    mask_path = tmp_path / "square_mask.png"
    image = Image.new("L", (5, 5), color=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 3, 3), fill=0)
    image.save(mask_path)

    coordinates, width, height = get_valid_coordinates(str(mask_path))
    distance_by_position = {(x, y): distance for x, y, distance in coordinates}

    assert (width, height) == (5, 5)
    assert len(coordinates) == 9
    assert distance_by_position[(2, 2)] == pytest.approx(1.0)
    assert distance_by_position[(1, 1)] == pytest.approx(0.5)
    assert distance_by_position[(2, 2)] > distance_by_position[(1, 1)]


def test_threshold_controls_foreground_selection(tmp_path) -> None:
    mask_path = tmp_path / "threshold_mask.png"
    image = Image.new("L", (3, 1), color=255)
    image.putpixel((0, 0), 20)
    image.putpixel((1, 0), 140)
    image.save(mask_path)

    dark_only, _, _ = get_valid_coordinates(str(mask_path), threshold=128)
    dark_and_mid, _, _ = get_valid_coordinates(str(mask_path), threshold=200)

    assert {(x, y) for x, y, _ in dark_only} == {(0, 0)}
    assert {(x, y) for x, y, _ in dark_and_mid} == {(0, 0), (1, 0)}


def test_empty_mask_raises_clear_error(tmp_path) -> None:
    mask_path = tmp_path / "empty_mask.png"
    Image.new("L", (4, 4), color=255).save(mask_path)

    with pytest.raises(ValueError, match="contains no pixels"):
        get_valid_coordinates(str(mask_path))


def test_invalid_threshold_is_rejected(tmp_path) -> None:
    mask_path = tmp_path / "mask.png"
    Image.new("L", (2, 2), color=0).save(mask_path)

    with pytest.raises(ValueError, match="threshold"):
        get_valid_coordinates(str(mask_path), threshold=300)


def test_missing_mask_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError, match="Mask file not found"):
        get_valid_coordinates("missing-mask.png")


def test_invalid_image_raises_clear_error(tmp_path) -> None:
    mask_path = tmp_path / "not-an-image.png"
    mask_path.write_text("not an image", encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to read mask image"):
        get_valid_coordinates(str(mask_path))
