
from pathlib import Path

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


class ImageAnalysisCache:
    """
    In-memory cache for image analysis results.

    Cache entries are identified by:
    - Resolved file path
    - File size
    - Last modification timestamp

    When a file changes, a new cache key is generated.
    """

    def __init__(self) -> None:
        self._sha256_cache: dict[tuple, str] = {}
        self._phash_cache: dict[tuple, imagehash.ImageHash] = {}
        self._histogram_cache: dict[tuple, ColorHistogram] = {}
        self._metadata_cache: dict[tuple, ImageMetadata] = {}

    @staticmethod
    def _get_cache_key(image: ImageInfo) -> tuple:
        path = Path(image.path).expanduser().resolve()
        stat = path.stat()

        return (
            str(path),
            stat.st_size,
            stat.st_mtime_ns,
        )

    def get_sha256(self, image: ImageInfo) -> str:
        key = self._get_cache_key(image)

        if key not in self._sha256_cache:
            self._sha256_cache[key] = calculate_sha256(image.path)

        return self._sha256_cache[key]

    def get_phash(self, image: ImageInfo) -> imagehash.ImageHash:
        key = self._get_cache_key(image)

        if key not in self._phash_cache:
            self._phash_cache[key] = calculate_phash(image.path)

        return self._phash_cache[key]

    def get_color_histogram(self, image: ImageInfo) -> ColorHistogram:
        key = self._get_cache_key(image)

        if key not in self._histogram_cache:
            self._histogram_cache[key] = calculate_color_histogram(
                image.path
            )

        return self._histogram_cache[key]

    def get_metadata(self, image: ImageInfo) -> ImageMetadata:
        key = self._get_cache_key(image)

        if key not in self._metadata_cache:
            self._metadata_cache[key] = extract_image_metadata(
                image.path
            )

        return self._metadata_cache[key]

    def clear(self) -> None:
        """Clear all cached analysis results."""
        self._sha256_cache.clear()
        self._phash_cache.clear()
        self._histogram_cache.clear()
        self._metadata_cache.clear()
