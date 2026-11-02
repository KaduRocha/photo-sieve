
from PIL import Image

from photosieve.scanner import ImageScanner


def test_scan_finds_supported_images(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    Image.new("RGB", (800, 600)).save(image_dir / "photo.jpg")
    Image.new("RGB", (400, 300)).save(image_dir / "photo.png")

    (image_dir / "document.txt").write_text("Not an image")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    assert result.total_images == 2
    assert result.files_examined == 2
    assert len(result.errors) == 0


def test_scan_finds_images_recursively(tmp_path):
    nested_dir = tmp_path / "photos" / "vacation"
    nested_dir.mkdir(parents=True)

    Image.new("RGB", (1920, 1080)).save(nested_dir / "photo.jpg")

    scanner = ImageScanner()
    result = scanner.scan(tmp_path / "photos")

    assert result.total_images == 1
    assert result.images_found[0].width == 1920
    assert result.images_found[0].height == 1080


def test_scan_identifies_corrupted_images(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    (image_dir / "corrupted.jpg").write_bytes(b"invalid image content")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    assert result.total_images == 0
    assert len(result.errors) == 1


def test_scan_calculates_total_size(tmp_path):
    image_dir = tmp_path / "photos"
    image_dir.mkdir()

    Image.new("RGB", (100, 100)).save(image_dir / "photo.jpg")

    scanner = ImageScanner()
    result = scanner.scan(image_dir)

    expected_size = (image_dir / "photo.jpg").stat().st_size

    assert result.total_size_bytes == expected_size
