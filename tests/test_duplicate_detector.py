
from PIL import Image

from photosieve.scanner import ImageScanner
from photosieve.duplicate_detector import find_exact_duplicates


def test_finds_exact_duplicates(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    image = Image.new("RGB", (100, 100), color="red")

    image.save(image_dir / "photo_a.png")
    image.save(image_dir / "photo_b.png")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    groups = find_exact_duplicates(result.images_found)

    assert len(groups) == 1
    assert len(groups[0].images) == 2


def test_different_images_are_not_duplicates(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    Image.new("RGB", (100, 100), color="red").save(
        image_dir / "photo_a.png"
    )

    Image.new("RGB", (100, 100), color="blue").save(
        image_dir / "photo_b.png"
    )

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    groups = find_exact_duplicates(result.images_found)

    assert len(groups) == 0


def test_calculates_recoverable_space(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    image = Image.new("RGB", (100, 100), color="green")

    image.save(image_dir / "photo_a.png")
    image.save(image_dir / "photo_b.png")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    groups = find_exact_duplicates(result.images_found)

    assert len(groups) == 1
    assert groups[0].reclaimable_bytes == groups[0].images[0].size_bytes
