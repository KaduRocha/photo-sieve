
import shutil

import pytest
from PIL import Image, ImageDraw

from photosieve.comparison.hybrid_detector import (
    compare_images,
    find_hybrid_similarities,
)
from photosieve.scanner import ImageScanner


def scan_images(directory):
    return ImageScanner().scan(directory).images_found


def test_identifies_exact_duplicates(tmp_path):
    image_a = tmp_path / "photo_a.png"
    image_b = tmp_path / "photo_b.png"

    Image.new("RGB", (200, 200), color="red").save(image_a)
    shutil.copyfile(image_a, image_b)

    images = scan_images(tmp_path)

    result = compare_images(images[0], images[1])

    assert result.is_exact_duplicate is True
    assert result.classification == "EXACT_DUPLICATE"
    assert result.similarity_score == 1.0


def test_identifies_very_high_similarity(tmp_path):
    image_a = tmp_path / "original.png"
    image_b = tmp_path / "modified.png"

    Image.new("RGB", (256, 256), color="red").save(image_a)

    modified = Image.new("RGB", (256, 256), color="red")
    draw = ImageDraw.Draw(modified)
    draw.rectangle((0, 0, 3, 3), fill="green")
    modified.save(image_b)

    images = scan_images(tmp_path)

    result = compare_images(images[0], images[1])

    assert result.is_exact_duplicate is False
    assert result.classification == "VERY_HIGH_SIMILARITY"
    assert result.similarity_score >= 0.95


def test_different_colors_are_not_classified_as_high_similarity(tmp_path):
    image_a = tmp_path / "red.png"
    image_b = tmp_path / "blue.png"

    Image.new("RGB", (200, 200), color="red").save(image_a)
    Image.new("RGB", (200, 200), color="blue").save(image_b)

    images = scan_images(tmp_path)

    result = compare_images(images[0], images[1])

    assert result.classification not in {
        "VERY_HIGH_SIMILARITY",
        "HIGH_SIMILARITY",
    }


def test_finds_hybrid_similarities(tmp_path):
    image_a = tmp_path / "original.png"
    image_b = tmp_path / "modified.png"
    image_c = tmp_path / "different.png"

    Image.new("RGB", (256, 256), color="red").save(image_a)

    modified = Image.new("RGB", (256, 256), color="red")
    ImageDraw.Draw(modified).rectangle(
        (0, 0, 3, 3),
        fill="green",
    )
    modified.save(image_b)

    Image.new("RGB", (256, 256), color="blue").save(image_c)

    images = scan_images(tmp_path)

    results = find_hybrid_similarities(images)

    assert len(results) >= 1
    assert any(
        comparison.classification == "VERY_HIGH_SIMILARITY"
        for comparison in results
    )


def test_returns_empty_for_less_than_two_images(tmp_path):
    image_path = tmp_path / "single.png"
    Image.new("RGB", (100, 100), color="red").save(image_path)

    images = scan_images(tmp_path)

    assert find_hybrid_similarities(images) == []


def test_rejects_invalid_phash_threshold(tmp_path):
    with pytest.raises(ValueError):
        find_hybrid_similarities([], phash_threshold=65)


def test_rejects_invalid_minimum_score():
    with pytest.raises(ValueError):
        find_hybrid_similarities([], minimum_score=1.5)
