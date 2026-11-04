
from dataclasses import dataclass, field


def hamming_distance(hash_a: int, hash_b: int) -> int:
    """Calculate the Hamming distance between two integer hashes."""
    return (hash_a ^ hash_b).bit_count()


@dataclass
class BKTreeNode:
    value: int
    indexes: list[int] = field(default_factory=list)
    children: dict[int, "BKTreeNode"] = field(default_factory=dict)


class BKTree:
    """
    BK-Tree index for integer hashes using Hamming distance.

    Each node stores a hash value and the indexes of images
    that share that exact hash.
    """

    def __init__(self) -> None:
        self.root: BKTreeNode | None = None

    def add(self, value: int, index: int) -> None:
        if self.root is None:
            self.root = BKTreeNode(
                value=value,
                indexes=[index],
            )
            return

        current = self.root

        while True:
            distance = hamming_distance(value, current.value)

            if distance == 0:
                current.indexes.append(index)
                return

            child = current.children.get(distance)

            if child is None:
                current.children[distance] = BKTreeNode(
                    value=value,
                    indexes=[index],
                )
                return

            current = child

    def search(
        self,
        value: int,
        max_distance: int,
    ) -> list[tuple[int, int]]:
        """
        Return matching indexes and their distances.

        Only nodes within the requested Hamming distance are returned.
        """
        if max_distance < 0:
            raise ValueError("Maximum distance cannot be negative.")

        if self.root is None:
            return []

        matches = []
        pending = [self.root]

        while pending:
            current = pending.pop()

            distance = hamming_distance(value, current.value)

            if distance <= max_distance:
                matches.extend(
                    (index, distance)
                    for index in current.indexes
                )

            lower_bound = distance - max_distance
            upper_bound = distance + max_distance

            for edge_distance, child in current.children.items():
                if lower_bound <= edge_distance <= upper_bound:
                    pending.append(child)

        return matches
