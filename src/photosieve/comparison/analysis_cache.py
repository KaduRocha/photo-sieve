
from collections.abc import Callable
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
from photosieve.hasher import calculate_sha256
from photosieve.image_analyzer import calculate_phash
from photosieve.scanner import ImageInfo

T = TypeVar("T")
LOCK_STRIPES = 64


class ImageAnalysisCache:
    """
    Thread-safe in-memory cache for image analysis results.

    Cache entries are identified by resolved path, file size
    and last modification timestamp.

    Lock striping prevents duplicate calculations while
    keeping synchronization memory bounded.
    """

    def __init__(self) -> None:
        self._sha256_cache: dict[tuple, str] = {}
        self._phash_cache: dict[tuple, imagehash.ImageHash] = {}
        self._histogram_cache: dict[tuple, ColorHistogram] = {}
        self._metadata_cache: dict[tuple, ImageMetadata] = {}

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

            result = calculator()

            with self._lock:
                cache[key] = result

            return result

    def get_sha256(self, image: ImageInfo) -> str:
        return self._get_or_compute(
            self._sha256_cache,
            "sha256",
            image,
            lambda: calculate_sha256(image.path),
        )

    def get_phash(self, image: ImageInfo) -> imagehash.ImageHash:
        return self._get_or_compute(
            self._phash_cache,
            "phash",
            image,
            lambda: calculate_phash(image.path),
        )

    def get_color_histogram(self, image: ImageInfo) -> ColorHistogram:
        return self._get_or_compute(
            self._histogram_cache,
            "histogram",
            image,
            lambda: calculate_color_histogram(image.path),
        )

    def get_metadata(self, image: ImageInfo) -> ImageMetadata:
        return self._get_or_compute(
            self._metadata_cache,
            "metadata",
            image,
            lambda: extract_image_metadata(image.path),
        )

    def clear(self) -> None:
        """Clear all cached results when no analysis is running."""
        with self._lock:
            self._sha256_cache.clear()
            self._phash_cache.clear()
            self._histogram_cache.clear()
            self._metadata_cache.clear()
