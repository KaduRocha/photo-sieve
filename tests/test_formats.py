import pytest

from photosieve.formats import HEIC_EXTENSIONS, HEIC_SUPPORTED, SUPPORTED_EXTENSIONS
from photosieve.image_analyzer import calculate_phash
from photosieve.scanner import ImageScanner
from tests.conftest import make_scene


def test_heic_extensions_follow_availability():
    assert HEIC_EXTENSIONS <= SUPPORTED_EXTENSIONS if HEIC_SUPPORTED else True
    assert not (HEIC_EXTENSIONS & SUPPORTED_EXTENSIONS) or HEIC_SUPPORTED


@pytest.mark.skipif(not HEIC_SUPPORTED, reason="pillow-heif não instalado")
def test_heic_is_scanned_and_hashed(tmp_path):
    from PIL import Image

    directory = tmp_path / "heic"
    directory.mkdir()
    scene = make_scene(directory / "tmp.png", seed=5)
    scene.save(directory / "photo.heic", quality=90)
    (directory / "tmp.png").unlink()

    result = ImageScanner().scan(directory)

    assert result.total_images == 1
    assert result.images_found[0].extension == ".heic"
    assert result.errors == []

    # pHash do HEIC é próximo ao da imagem original.
    original = tmp_path / "orig.png"
    Image.open(directory / "photo.heic").convert("RGB").save(original)
    assert calculate_phash(directory / "photo.heic") - calculate_phash(original) <= 2


def test_heic_files_ignored_when_unsupported(tmp_path, monkeypatch):
    import photosieve.scanner as scanner_module

    monkeypatch.setattr(
        scanner_module,
        "SUPPORTED_EXTENSIONS",
        SUPPORTED_EXTENSIONS - HEIC_EXTENSIONS,
    )
    (tmp_path / "photo.heic").write_bytes(b"fake")

    result = ImageScanner().scan(tmp_path)

    assert result.files_examined == 0
