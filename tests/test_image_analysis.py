import numpy as np
import pytest
from PIL import Image, ImageDraw

from engine.image_analysis import (
    _chamfer_distance_transform,
    get_valid_coordinates,
)


def test_chamfer_distance_grows_toward_the_center() -> None:
    mask = np.zeros((5, 5), dtype=bool)
    mask[1:4, 1:4] = True

    distances = _chamfer_distance_transform(mask)

    assert distances[0, 0] == 0
    assert distances[1, 1] == pytest.approx(1.0)
    assert distances[2, 2] == pytest.approx(2.0)
    assert distances[2, 2] > distances[1, 1]


def test_canvas_outside_is_treated_as_background() -> None:
    mask = np.ones((3, 3), dtype=bool)

    distances = _chamfer_distance_transform(mask)

    assert distances[0, 0] == pytest.approx(1.0)
    assert distances[1, 1] == pytest.approx(2.0)


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
