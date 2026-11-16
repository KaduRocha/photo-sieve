
from collections import defaultdict
from dataclasses import dataclass

from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.scanner import ImageInfo


@dataclass
class DuplicateGroup:
    sha256: str
    images: list[ImageInfo]

    @property
    def total_size_bytes(self) -> int:
        return sum(image.size_bytes for image in self.images)

    @property
    def reclaimable_bytes(self) -> int:
        if not self.images:
            return 0

        # Keep one copy of the duplicated content.
        return self.total_size_bytes - max(
            image.size_bytes for image in self.images
        )


def find_exact_duplicates(
    images: list[ImageInfo],
    cache: ImageAnalysisCache | None = None,
) -> list[DuplicateGroup]:
    """
    Encontra grupos de arquivos binariamente idênticos.

    Se um `ImageAnalysisCache` for informado, os SHA-256 calculados
    aqui são reaproveitados por outras etapas (ex.: análise híbrida).
    """
    analysis_cache = cache or ImageAnalysisCache()

    # First stage: group images by file size.
    size_groups = defaultdict(list)

    for image in images:
        size_groups[image.size_bytes].append(image)

    duplicate_groups = []

    # Second stage: hash only files with matching sizes.
    for candidates in size_groups.values():

        if len(candidates) < 2:
            continue

        hash_groups = defaultdict(list)

        for image in candidates:
            file_hash = analysis_cache.get_sha256(image)
            hash_groups[file_hash].append(image)

        # Keep only groups with actual binary duplicates.
        for file_hash, matching_images in hash_groups.items():

            if len(matching_images) > 1:
                duplicate_groups.append(
                    DuplicateGroup(
                        sha256=file_hash,
                        images=matching_images,
                    )
                )

    return sorted(
        duplicate_groups,
        key=lambda group: group.reclaimable_bytes,
        reverse=True,
    )
