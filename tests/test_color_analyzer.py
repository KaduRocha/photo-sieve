
import pytest

from PIL import Image

from photosieve.comparison.color_analyzer import (
    calculate_color_histogram,
    calculate_color_similarity,
    compare_color_histograms,
)


def test_identical_images_have_full_color_similarity(tmp_path):
    image_a = tmp_path / "red_a.png"
    image_b = tmp_path / "red_b.png"

    Image.new("RGB", (200, 200), color="red").save(image_a)
    Image.new("RGB", (200, 200), color="red").save(image_b)

    similarity = calculate_color_similarity(image_a, image_b)

    assert similarity == pytest.approx(1.0)


def test_different_colors_have_lower_similarity(tmp_path):
    image_a = tmp_path / "red.png"
    image_b = tmp_path / "blue.png"

    Image.new("RGB", (200, 200), color="red").save(image_a)
    Image.new("RGB", (200, 200), color="blue").save(image_b)

    similarity = calculate_color_similarity(image_a, image_b)

    assert similarity < 0.90


def test_black_and_white_have_different_color_histograms(tmp_path):
    image_a = tmp_path / "black.png"
    image_b = tmp_path / "white.png"

    Image.new("RGB", (200, 200), color="black").save(image_a)
    Image.new("RGB", (200, 200), color="white").save(image_b)

    similarity = calculate_color_similarity(image_a, image_b)

    assert similarity < 0.90


def test_histogram_channels_are_normalized(tmp_path):
    image_path = tmp_path / "photo.png"

    Image.new("RGB", (200, 200), color="green").save(image_path)

    histogram = calculate_color_histogram(image_path)

    assert len(histogram) == 3

    for channel in histogram:
        assert sum(channel) == pytest.approx(1.0)


def test_invalid_histogram_dimensions():
    histogram_a = ((1.0, 0.0), (1.0, 0.0), (1.0, 0.0))
    histogram_b = ((1.0,), (1.0,), (1.0,))

    with pytest.raises(ValueError):
        compare_color_histograms(histogram_a, histogram_b)
