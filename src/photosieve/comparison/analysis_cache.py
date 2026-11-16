
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from typing import TypeVar

import imagehash

from photosieve.comparison.color_analyzer import (
    ColorHistogram,
    calculate_color_histogram,
)
from photosieve.comparison.metadata_analyzer import (
    ImageMetadata,
    extract_image_metadata,
)
from photosieve.comparison.persistent_store import PersistentStore
from photosieve.hasher import calculate_sha256
from photosieve.image_analyzer import (
    calculate_phash,
    calculate_transform_phashes,
    calculate_window_phashes,
)
from photosieve.scanner import ImageInfo

T = TypeVar("T")
LOCK_STRIPES = 64


def _decode_sha256(text: str) -> str:
    if len(text) != 64:
        raise ValueError("SHA-256 inválido")

    return text


def _decode_histogram(text: str) -> ColorHistogram:
    channels = json.loads(text)

    if len(channels) != 3:
        raise ValueError("Histograma inválido")

    return tuple(tuple(float(v) for v in channel) for channel in channels)


class ImageAnalysisCache:
    """
    Thread-safe in-memory cache for image analysis results.

    Cache entries are identified by resolved path, file size
    and last modification timestamp.

    Lock striping prevents duplicate calculations while
    keeping synchronization memory bounded.

    Se um `PersistentStore` for informado, os resultados também são
    gravados em disco (SQLite) e reaproveitados entre execuções.
    """

    def __init__(self, store: PersistentStore | None = None) -> None:
        self._store = store

        self._sha256_cache: dict[tuple, str] = {}
        self._phash_cache: dict[tuple, imagehash.ImageHash] = {}
        self._histogram_cache: dict[tuple, ColorHistogram] = {}
        self._metadata_cache: dict[tuple, ImageMetadata] = {}
        self._window_cache: dict[tuple, list[imagehash.ImageHash]] = {}
        self._transform_cache: dict[tuple, list[imagehash.ImageHash]] = {}

        self._lock = Lock()
        self._feature_locks = [
            Lock() for _ in range(LOCK_STRIPES)
        ]

    @staticmethod
    def _get_cache_key(image: ImageInfo) -> tuple:
        path = Path(image.path).expanduser().resolve()
        stat = path.stat()

        return (
            str(path),
            stat.st_size,
            stat.st_mtime_ns,
        )

    def _get_or_compute(
        self,
        cache: dict[tuple, T],
        feature: str,
        image: ImageInfo,
        calculator: Callable[[], T],
        encode: Callable[[T], str] | None = None,
        decode: Callable[[str], T] | None = None,
    ) -> T:
        key = self._get_cache_key(image)

        with self._lock:
            if key in cache:
                return cache[key]

        lock_index = hash((feature, key)) % LOCK_STRIPES
        feature_lock = self._feature_locks[lock_index]

        with feature_lock:
            with self._lock:
                if key in cache:
                    return cache[key]

            result = None
            loaded = False

            if self._store is not None and decode is not None:
                stored = self._store.get(key, feature)

                if stored is not None:
                    try:
                        result = decode(stored)
                        loaded = True
                    except (ValueError, KeyError, TypeError):
                        loaded = False  # entrada corrompida: recalcula

            if not loaded:
                result = calculator()

                if self._store is not None and encode is not None:
                    self._store.put(key, feature, encode(result))

            with self._lock:
                cache[key] = result

            return result

    def get_sha256(self, image: ImageInfo) -> str:
        return self._get_or_compute(
            self._sha256_cache,
            "sha256",
            image,
            lambda: calculate_sha256(image.path),
            encode=str,
            decode=_decode_sha256,
        )

    def get_phash(self, image: ImageInfo) -> imagehash.ImageHash:
        return self._get_or_compute(
            self._phash_cache,
            "phash",
            image,
            lambda: calculate_phash(image.path),
            encode=str,
            decode=imagehash.hex_to_hash,
        )

    def get_color_histogram(self, image: ImageInfo) -> ColorHistogram:
        return self._get_or_compute(
            self._histogram_cache,
            "histogram",
            image,
            lambda: calculate_color_histogram(image.path),
            encode=json.dumps,
            decode=_decode_histogram,
        )

    def get_metadata(self, image: ImageInfo) -> ImageMetadata:
        return self._get_or_compute(
            self._metadata_cache,
            "metadata",
            image,
            lambda: extract_image_metadata(image.path),
            encode=lambda metadata: json.dumps(asdict(metadata)),
            decode=lambda text: ImageMetadata(**json.loads(text)),
        )

    def get_window_phashes(
        self,
        image: ImageInfo,
    ) -> list[imagehash.ImageHash]:
        """pHash de janelas internas, usado na detecção de recortes."""
        return self._get_or_compute(
            self._window_cache,
            "window_phashes_v2",  # v2: inclui janelas de proporção livre
            image,
            lambda: calculate_window_phashes(image.path),
            encode=lambda hashes: json.dumps([str(h) for h in hashes]),
            decode=lambda text: [
                imagehash.hex_to_hash(item) for item in json.loads(text)
            ],
        )

    def get_transform_phashes(
        self,
        image: ImageInfo,
    ) -> list[imagehash.ImageHash]:
        """pHash das variantes giradas/espelhadas, usado em --detect-transforms."""
        return self._get_or_compute(
            self._transform_cache,
            "transform_phashes",
            image,
            lambda: calculate_transform_phashes(image.path),
            encode=lambda hashes: json.dumps([str(h) for h in hashes]),
            decode=lambda text: [
                imagehash.hex_to_hash(item) for item in json.loads(text)
            ],
        )

    def clear(self) -> None:
        """Clear all cached results when no analysis is running."""
        with self._lock:
            self._sha256_cache.clear()
            self._phash_cache.clear()
            self._histogram_cache.clear()
            self._metadata_cache.clear()
            self._window_cache.clear()
            self._transform_cache.clear()
