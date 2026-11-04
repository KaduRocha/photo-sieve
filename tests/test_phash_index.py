
import random

from photosieve.comparison.phash_index import (
    BKTree,
    hamming_distance,
)


def test_calculates_hamming_distance():
    assert hamming_distance(0b0000, 0b0000) == 0
    assert hamming_distance(0b0000, 0b1111) == 4
    assert hamming_distance(0b1010, 0b1001) == 2


def test_empty_tree_returns_no_matches():
    tree = BKTree()

    assert tree.search(123, 5) == []


def test_search_returns_hashes_within_distance():
    tree = BKTree()

    tree.add(0b0000, 0)
    tree.add(0b0001, 1)
    tree.add(0b0011, 2)
    tree.add(0b1111, 3)

    results = tree.search(0b0000, 2)

    indexes = {index for index, _ in results}

    assert indexes == {0, 1, 2}


def test_tree_handles_identical_hashes():
    tree = BKTree()

    tree.add(12345, 0)
    tree.add(12345, 1)
    tree.add(12345, 2)

    results = tree.search(12345, 0)

    indexes = {index for index, _ in results}

    assert indexes == {0, 1, 2}


def test_tree_matches_brute_force_results():
    random.seed(42)

    values = [
        random.getrandbits(64)
        for _ in range(100)
    ]

    tree = BKTree()

    for index, value in enumerate(values):
        tree.add(value, index)

    query = random.getrandbits(64)
    threshold = 12

    indexed_results = {
        index
        for index, _ in tree.search(query, threshold)
    }

    brute_force_results = {
        index
        for index, value in enumerate(values)
        if hamming_distance(query, value) <= threshold
    }

    assert indexed_results == brute_force_results


def test_exact_duplicates_are_preserved_outside_phash_threshold():
    from photosieve.comparison.hybrid_detector import (
        _find_candidate_pairs,
    )

    pairs = _find_candidate_pairs(
        hashes=[0, 65535],
        sha256_hashes=["same-hash", "same-hash"],
        phash_threshold=0,
    )

    assert pairs == [(0, 1)]
