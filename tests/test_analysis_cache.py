
from PIL import Image

from photosieve.comparison import analysis_cache
from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.scanner import ImageScanner


def create_image(tmp_path):
    image_path = tmp_path / "photo.png"

    Image.new("RGB", (100, 100), color="red").save(image_path)

    image = ImageScanner().scan(tmp_path).images_found[0]

    return image


def test_sha256_is_calculated_only_once(tmp_path, monkeypatch):
    image = create_image(tmp_path)
    cache = ImageAnalysisCache()

    calls = 0

    def fake_sha256(path):
        nonlocal calls
        calls += 1
        return "test-hash"

    monkeypatch.setattr(
        analysis_cache,
        "calculate_sha256",
        fake_sha256,
    )

    first = cache.get_sha256(image)
    second = cache.get_sha256(image)

    assert first == second == "test-hash"
    assert calls == 1


def test_phash_is_calculated_only_once(tmp_path, monkeypatch):
    image = create_image(tmp_path)
    cache = ImageAnalysisCache()

    calls = 0

    def fake_phash(path):
        nonlocal calls
        calls += 1
        return "test-phash"

    monkeypatch.setattr(
        analysis_cache,
        "calculate_phash",
        fake_phash,
    )

    first = cache.get_phash(image)
    second = cache.get_phash(image)

    assert first == second == "test-phash"
    assert calls == 1


def test_cache_invalidates_when_file_changes(tmp_path, monkeypatch):
    image = create_image(tmp_path)
    cache = ImageAnalysisCache()

    calls = 0

    def fake_sha256(path):
        nonlocal calls
        calls += 1
        return f"hash-{calls}"

    monkeypatch.setattr(
        analysis_cache,
        "calculate_sha256",
        fake_sha256,
    )

    first = cache.get_sha256(image)

    with open(image.path, "ab") as file:
        file.write(b"modified")

    second = cache.get_sha256(image)

    assert first == "hash-1"
    assert second == "hash-2"
    assert calls == 2


def test_clear_removes_cached_results(tmp_path, monkeypatch):
    image = create_image(tmp_path)
    cache = ImageAnalysisCache()

    calls = 0

    def fake_sha256(path):
        nonlocal calls
        calls += 1
        return "test-hash"

    monkeypatch.setattr(
        analysis_cache,
        "calculate_sha256",
        fake_sha256,
    )

    cache.get_sha256(image)
    cache.clear()
    cache.get_sha256(image)

    assert calls == 2
