
from PIL import Image

from photosieve.comparison.metadata_analyzer import (
    extract_image_metadata,
)


def test_extracts_basic_image_metadata(tmp_path):
    image_path = tmp_path / "photo.png"

    Image.new("RGB", (1920, 1080), color="red").save(image_path)

    metadata = extract_image_metadata(image_path)

    assert metadata.width == 1920
    assert metadata.height == 1080
    assert metadata.format == "PNG"
    assert metadata.mode == "RGB"
    assert metadata.megapixels == 2.07
    assert metadata.aspect_ratio == 1.7778
    assert metadata.has_transparency is False


def test_extracts_transparency(tmp_path):
    image_path = tmp_path / "transparent.png"

    Image.new("RGBA", (100, 100), color=(255, 0, 0, 128)).save(image_path)

    metadata = extract_image_metadata(image_path)

    assert metadata.has_transparency is True


def test_missing_exif_returns_none(tmp_path):
    image_path = tmp_path / "no_exif.jpg"

    Image.new("RGB", (800, 600), color="blue").save(image_path)

    metadata = extract_image_metadata(image_path)

    assert metadata.camera_make is None
    assert metadata.camera_model is None
    assert metadata.date_taken is None
    assert metadata.orientation is None


def test_extracts_image_format(tmp_path):
    image_path = tmp_path / "photo.webp"

    Image.new("RGB", (400, 300), color="green").save(
        image_path,
        format="WEBP",
    )

    metadata = extract_image_metadata(image_path)

    assert metadata.format == "WEBP"
    assert metadata.width == 400
    assert metadata.height == 300


def test_calculates_megapixels(tmp_path):
    image_path = tmp_path / "large.png"

    Image.new("RGB", (4000, 3000), color="white").save(image_path)

    metadata = extract_image_metadata(image_path)

    assert metadata.megapixels == 12.0
