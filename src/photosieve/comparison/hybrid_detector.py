
# from dataclasses import dataclass

# from photosieve.comparison.color_analyzer import (
#     calculate_color_histogram,
#     compare_color_histograms,
# )
# from photosieve.comparison.metadata_analyzer import (
#     ImageMetadata,
#     extract_image_metadata,
# )
# from photosieve.hasher import calculate_sha256
# from photosieve.image_analyzer import calculate_phash
# from photosieve.scanner import ImageInfo


from dataclasses import dataclass

from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.color_analyzer import compare_color_histograms
from photosieve.comparison.metadata_analyzer import ImageMetadata
from photosieve.comparison.phash_index import BKTree
from photosieve.scanner import ImageInfo

HASH_BITS = 64

PHASH_WEIGHT = 0.55
COLOR_WEIGHT = 0.35
METADATA_WEIGHT = 0.10

VERY_HIGH_THRESHOLD = 0.95
HIGH_THRESHOLD = 0.85
POSSIBLE_THRESHOLD = 0.70


@dataclass
class HybridComparison:
    image_a: ImageInfo
    image_b: ImageInfo
    classification: str
    similarity_score: float
    phash_distance: int
    color_similarity: float
    metadata_similarity: float
    is_exact_duplicate: bool

    @property
    def similarity_percent(self) -> float:
        return round(self.similarity_score * 100, 2)


def _calculate_metadata_similarity(
    metadata_a: ImageMetadata,
    metadata_b: ImageMetadata,
) -> float:
    """
    Compare image aspect ratios.

    Image dimensions may differ because of resizing or compression.
    Therefore, aspect ratio is used instead of requiring equal dimensions.
    """
    ratio_a = metadata_a.aspect_ratio
    ratio_b = metadata_b.aspect_ratio

    if ratio_a <= 0 or ratio_b <= 0:
        return 0.0

    difference = abs(ratio_a - ratio_b) / max(ratio_a, ratio_b)

    if difference <= 0.01:
        return 1.0

    if difference <= 0.03:
        return 0.75

    if difference <= 0.08:
        return 0.40

    return 0.0


def _classify_similarity(
    score: float,
    is_exact_duplicate: bool,
) -> str:
    if is_exact_duplicate:
        return "EXACT_DUPLICATE"

    if score >= VERY_HIGH_THRESHOLD:
        return "VERY_HIGH_SIMILARITY"

    if score >= HIGH_THRESHOLD:
        return "HIGH_SIMILARITY"

    if score >= POSSIBLE_THRESHOLD:
        return "POSSIBLE_SIMILARITY"

    return "NOT_SIMILAR"



def compare_images(
    image_a: ImageInfo,
    image_b: ImageInfo,
    cache: ImageAnalysisCache | None = None,
) -> HybridComparison:
    """
    Compare two images using cached SHA-256, pHash,
    color histogram and metadata results.
    """
    analysis_cache = cache or ImageAnalysisCache()

    sha256_a = analysis_cache.get_sha256(image_a)
    sha256_b = analysis_cache.get_sha256(image_b)

    is_exact_duplicate = sha256_a == sha256_b

    phash_a = analysis_cache.get_phash(image_a)
    phash_b = analysis_cache.get_phash(image_b)

    phash_distance = int(phash_a - phash_b)

    if is_exact_duplicate:
        return HybridComparison(
            image_a=image_a,
            image_b=image_b,
            classification="EXACT_DUPLICATE",
            similarity_score=1.0,
            phash_distance=phash_distance,
            color_similarity=1.0,
            metadata_similarity=1.0,
            is_exact_duplicate=True,
        )

    histogram_a = analysis_cache.get_color_histogram(image_a)
    histogram_b = analysis_cache.get_color_histogram(image_b)

    color_similarity = compare_color_histograms(
        histogram_a,
        histogram_b,
    )

    metadata_a = analysis_cache.get_metadata(image_a)
    metadata_b = analysis_cache.get_metadata(image_b)

    metadata_similarity = _calculate_metadata_similarity(
        metadata_a,
        metadata_b,
    )

    phash_similarity = (
        HASH_BITS - phash_distance
    ) / HASH_BITS

    similarity_score = (
        phash_similarity * PHASH_WEIGHT
        + color_similarity * COLOR_WEIGHT
        + metadata_similarity * METADATA_WEIGHT
    )

    similarity_score = max(0.0, min(1.0, similarity_score))

    classification = _classify_similarity(
        similarity_score,
        is_exact_duplicate,
    )

    return HybridComparison(
        image_a=image_a,
        image_b=image_b,
        classification=classification,
        similarity_score=similarity_score,
        phash_distance=phash_distance,
        color_similarity=color_similarity,
        metadata_similarity=metadata_similarity,
        is_exact_duplicate=False,
    )

def _to_integer_hash(image_hash) -> int:
    """Convert an ImageHash or integer into an integer hash."""
    if isinstance(image_hash, int):
        return image_hash

    return int(str(image_hash), 16)

def _find_candidate_pairs(
    hashes: list,
    sha256_hashes: list[str],
    phash_threshold: int,
) -> list[tuple[int, int]]:
    """
    Generate candidate image pairs using BK-Tree indexing.

    Exact duplicates are always included, independently
    of the perceptual hash threshold.
    """
    index = BKTree()

    for image_index, image_hash in enumerate(hashes):
        index.add(_to_integer_hash(image_hash), image_index)

    candidate_pairs = set()

    for index_a, image_hash in enumerate(hashes):
        matches = index.search(
            _to_integer_hash(image_hash),
            max_distance=phash_threshold,
        )

        for index_b, _ in matches:
            if index_b > index_a:
                candidate_pairs.add((index_a, index_b))

    # Preserve exact duplicate detection even if the pHash
    # threshold would otherwise exclude a pair.
    exact_groups = {}

    for image_index, file_hash in enumerate(sha256_hashes):
        exact_groups.setdefault(file_hash, []).append(image_index)

    for indexes in exact_groups.values():
        if len(indexes) < 2:
            continue

        for position, index_a in enumerate(indexes):
            for index_b in indexes[position + 1:]:
                candidate_pairs.add((index_a, index_b))

    return sorted(candidate_pairs)



def find_hybrid_similarities(
    images: list[ImageInfo],
    phash_threshold: int = 12,
    minimum_score: float = POSSIBLE_THRESHOLD,
    cache: ImageAnalysisCache | None = None,
) -> list[HybridComparison]:
    """
    Find potentially similar image pairs using hybrid analysis.

    SHA-256 identifies exact duplicates.
    pHash filters candidate pairs.
    Cached results prevent repeated file analysis.
    """
    if not 0 <= phash_threshold <= HASH_BITS:
        raise ValueError(
            f"pHash threshold must be between 0 and {HASH_BITS}."
        )

    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError(
            "Minimum score must be between 0.0 and 1.0."
        )

    if len(images) < 2:
        return []

    analysis_cache = cache or ImageAnalysisCache()

    hashes = [
        analysis_cache.get_phash(image)
        for image in images
    ]

    sha256_hashes = [
        analysis_cache.get_sha256(image)
        for image in images
    ]

    comparisons = []


    candidate_pairs = _find_candidate_pairs(
        hashes=hashes,
        sha256_hashes=sha256_hashes,
        phash_threshold=phash_threshold,
    )

    comparisons = []

    for index_a, index_b in candidate_pairs:
        comparison = compare_images(
            images[index_a],
            images[index_b],
            cache=analysis_cache,
        )

        if (
            comparison.is_exact_duplicate
            or comparison.similarity_score >= minimum_score
        ):
            comparisons.append(comparison)


    return sorted(
        comparisons,
        key=lambda comparison: (
            not comparison.is_exact_duplicate,
            -comparison.similarity_score,
        ),
    )

