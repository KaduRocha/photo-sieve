
from dataclasses import dataclass

from photosieve.image_analyzer import calculate_phash
from photosieve.scanner import ImageInfo

HASH_BITS = 64


@dataclass
class SimilarityGroup:
    images: list[ImageInfo]
    max_distance: int

    @property
    def similarity_percent(self) -> float:
        return ((HASH_BITS - self.max_distance) / HASH_BITS) * 100

    @property
    def classification(self) -> str:
        if self.max_distance == 0:
            return "Perceptually identical"

        return "Visually similar"


def find_similarity_groups(
    images: list[ImageInfo],
    threshold: int = 6,
) -> list[SimilarityGroup]:
    """
    Group visually similar images using complete-link clustering.

    Every image in a group must be within the threshold distance
    of every other image in that same group.

    This prevents transitive chaining between dissimilar images.
    """
    if not 0 <= threshold <= HASH_BITS:
        raise ValueError(
            f"Threshold must be between 0 and {HASH_BITS}."
        )

    if len(images) < 2:
        return []

    hashes = [
        calculate_phash(image.path)
        for image in images
    ]

    distances = {}
    candidate_pairs = []

    # Calculate the Hamming distance between every pair.
    for i in range(len(images)):
        for j in range(i + 1, len(images)):
            distance = hashes[i] - hashes[j]

            distances[(i, j)] = distance

            if distance <= threshold:
                candidate_pairs.append((distance, i, j))

    # Process the closest pairs first.
    candidate_pairs.sort()

    # Initially, every image belongs to its own cluster.
    clusters = {
        index: [index]
        for index in range(len(images))
    }

    cluster_ids = list(range(len(images)))
    # next_cluster_id = len(images)

    for _, index_a, index_b in candidate_pairs:
        cluster_a = cluster_ids[index_a]
        cluster_b = cluster_ids[index_b]

        if cluster_a == cluster_b:
            continue

        members_a = clusters[cluster_a]
        members_b = clusters[cluster_b]

        # Complete-link rule:
        # Every cross-cluster pair must satisfy the threshold.
        can_merge = all(
            distances[
                (min(a, b), max(a, b))
            ] <= threshold
            for a in members_a
            for b in members_b
        )

        if not can_merge:
            continue

        # Merge cluster_b into cluster_a.
        clusters[cluster_a].extend(members_b)
        del clusters[cluster_b]

        for member in members_b:
            cluster_ids[member] = cluster_a

        # next_cluster_id += 1

    groups = []

    for members in clusters.values():
        if len(members) < 2:
            continue

        group_distances = [
            distances[(min(a, b), max(a, b))]
            for position, a in enumerate(members)
            for b in members[position + 1:]
        ]

        groups.append(
            SimilarityGroup(
                images=[images[index] for index in members],
                max_distance=int(max(group_distances)),
            )
        )

    return sorted(
        groups,
        key=lambda group: (
            -len(group.images),
            group.max_distance,
        ),
    )
