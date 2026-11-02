
from types import SimpleNamespace

import pytest

from PIL import Image

from photosieve.scanner import ImageScanner
from photosieve.similarity_detector import find_similarity_groups


def test_groups_visually_identical_images(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    image_a = image_dir / "photo_a.png"
    image_b = image_dir / "photo_b.png"

    Image.new("RGB", (200, 200), color="red").save(image_a)
    image_b.write_bytes(image_a.read_bytes())

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    groups = find_similarity_groups(
        result.images_found,
        threshold=4,
    )

    assert len(groups) == 1
    assert len(groups[0].images) == 2
    assert groups[0].max_distance == 0
    assert groups[0].classification == "Perceptually identical"



def test_does_not_group_dissimilar_images(tmp_path):
    from PIL import ImageDraw

    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    red_image = Image.new(
        "RGB",
        (200, 200),
        color="red",
    )

    blue_image = Image.new(
        "RGB",
        (200, 200),
        color="blue",
    )

    draw = ImageDraw.Draw(blue_image)

    # Add a checkerboard pattern to create
    # a clearly different visual structure.
    square_size = 25

    for row in range(8):
        for column in range(8):
            if (row + column) % 2 == 0:
                x1 = column * square_size
                y1 = row * square_size
                x2 = x1 + square_size - 1
                y2 = y1 + square_size - 1

                draw.rectangle(
                    (x1, y1, x2, y2),
                    fill="white",
                )

    red_image.save(image_dir / "red.png")
    blue_image.save(image_dir / "blue.png")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    groups = find_similarity_groups(
        result.images_found,
        threshold=0,
    )

    assert groups == []



def test_prevents_transitive_chaining(monkeypatch):
    import photosieve.similarity_detector as detector

    images = [
        SimpleNamespace(path="a.png"),
        SimpleNamespace(path="b.png"),
        SimpleNamespace(path="c.png"),
    ]

    distances = {
        ("a.png", "b.png"): 1,
        ("a.png", "c.png"): 10,
        ("b.png", "c.png"): 1,
    }

    class FakeHash:
        def __init__(self, path):
            self.path = path

        def __sub__(self, other):
            key = tuple(sorted((self.path, other.path)))
            return distances[key]

    monkeypatch.setattr(
        detector,
        "calculate_phash",
        lambda path: FakeHash(path),
    )

    groups = find_similarity_groups(
        images,
        threshold=2,
    )

    assert len(groups) == 1
    assert len(groups[0].images) == 2

    grouped_paths = {
        image.path
        for image in groups[0].images
    }

    assert grouped_paths == {"a.png", "b.png"}


def test_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        find_similarity_groups([], threshold=65)
