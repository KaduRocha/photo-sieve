import os
import sqlite3

import pytest

from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.persistent_store import PersistentStore
from photosieve.scanner import ImageScanner
from tests.conftest import make_image


@pytest.fixture
def one_image(tmp_path):
    directory = tmp_path / "imgs"
    directory.mkdir()
    make_image(directory / "a.png", "red", stripe="blue")

    return ImageScanner().scan(directory).images_found[0]


def test_store_roundtrip_and_cleanup_of_old_versions(tmp_path):
    with PersistentStore(tmp_path / "c.db") as store:
        key_old = ("/x.jpg", 10, 1)
        key_new = ("/x.jpg", 11, 2)

        store.put(key_old, "sha256", "old")
        assert store.get(key_old, "sha256") == "old"
        assert store.get(key_new, "sha256") is None

        store.put(key_new, "sha256", "new")

        assert store.get(key_old, "sha256") is None
        assert store.count() == 1

        store.clear()
        assert store.count() == 0


def test_second_run_uses_disk_without_recomputing(tmp_path, one_image, monkeypatch):
    import photosieve.comparison.analysis_cache as module

    db = tmp_path / "cache.db"

    with PersistentStore(db) as store:
        cache = ImageAnalysisCache(store)
        first = (
            cache.get_sha256(one_image),
            cache.get_phash(one_image),
            cache.get_color_histogram(one_image),
            cache.get_metadata(one_image),
            cache.get_window_phashes(one_image),
        )

    def fail(*args, **kwargs):
        raise AssertionError("não deveria recalcular")

    for name in (
        "calculate_sha256",
        "calculate_phash",
        "calculate_color_histogram",
        "extract_image_metadata",
        "calculate_window_phashes",
    ):
        monkeypatch.setattr(module, name, fail)

    with PersistentStore(db) as store:
        cache = ImageAnalysisCache(store)
        second = (
            cache.get_sha256(one_image),
            cache.get_phash(one_image),
            cache.get_color_histogram(one_image),
            cache.get_metadata(one_image),
            cache.get_window_phashes(one_image),
        )

    assert first == second


def test_modified_file_invalidates_entry(tmp_path, one_image):
    db = tmp_path / "cache.db"

    with PersistentStore(db) as store:
        old_sha = ImageAnalysisCache(store).get_sha256(one_image)

    make_image(one_image.path, "green", stripe="white")
    os.utime(one_image.path, ns=(1, 1))

    with PersistentStore(db) as store:
        new_sha = ImageAnalysisCache(store).get_sha256(one_image)

    assert new_sha != old_sha


def test_corrupted_entry_is_recomputed(tmp_path, one_image):
    db = tmp_path / "cache.db"

    with PersistentStore(db) as store:
        expected = ImageAnalysisCache(store).get_sha256(one_image)

    connection = sqlite3.connect(db)
    connection.execute("UPDATE analysis SET value = 'lixo' WHERE feature = 'sha256'")
    connection.commit()
    connection.close()

    with PersistentStore(db) as store:
        assert ImageAnalysisCache(store).get_sha256(one_image) == expected


def test_incompatible_schema_is_rebuilt(tmp_path):
    db = tmp_path / "cache.db"

    with PersistentStore(db) as store:
        store.put(("/a", 1, 1), "sha256", "x")

    connection = sqlite3.connect(db)
    connection.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
    connection.commit()
    connection.close()

    with PersistentStore(db) as store:
        assert store.count() == 0
