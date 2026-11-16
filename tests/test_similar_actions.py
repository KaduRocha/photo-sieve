import pytest
from PIL import Image

from photosieve.comparison.hybrid_detector import find_hybrid_similarities
from photosieve.file_manager import (
    ActionKind,
    choose_best_quality,
    execute_actions,
    plan_similar_actions,
)
from photosieve.scanner import ImageScanner
from tests.conftest import make_scene


@pytest.fixture
def library(tmp_path):
    directory = tmp_path / "lib"
    directory.mkdir()
    big = make_scene(directory / "big.png", seed=3, size=(400, 400))
    big.resize((200, 200)).save(directory / "small.jpg", quality=80)
    make_scene(directory / "unrelated.png", seed=777)

    result = ImageScanner().scan(directory)
    comparisons = find_hybrid_similarities(result.images_found)

    return directory, result, comparisons


def test_keeps_highest_resolution(library, tmp_path):
    directory, _, comparisons = library

    actions = plan_similar_actions(
        comparisons, directory, quarantine_directory=tmp_path / "q", minimum_score=0.9
    )

    assert [a.kept.filename for a in actions] == ["big.png"]
    assert [a.target.filename for a in actions] == ["small.jpg"]
    assert not actions[0].exact
    assert actions[0].similarity_percent > 90


def test_minimum_score_filters_pairs(library, tmp_path):
    directory, _, comparisons = library

    assert plan_similar_actions(
        comparisons, directory, quarantine_directory=tmp_path / "q", minimum_score=1.0
    ) == []


def test_apply_moves_only_the_lower_quality_copy(library, tmp_path):
    directory, _, comparisons = library
    actions = plan_similar_actions(
        comparisons, directory, quarantine_directory=tmp_path / "q"
    )

    report = execute_actions(actions, apply=True)

    assert len(report.processed) == 1
    assert (directory / "big.png").exists()
    assert (directory / "unrelated.png").exists()
    assert not (directory / "small.jpg").exists()
    assert (tmp_path / "q" / "small.jpg").exists()


def test_similar_images_cannot_be_deleted(library, tmp_path):
    directory, _, comparisons = library
    actions = plan_similar_actions(
        comparisons, directory, quarantine_directory=tmp_path / "q"
    )

    with pytest.raises(ValueError):
        execute_actions(actions, kind=ActionKind.DELETE, apply=True)

    assert (directory / "small.jpg").exists()


def test_changed_file_is_skipped(library, tmp_path):
    directory, _, comparisons = library
    actions = plan_similar_actions(
        comparisons, directory, quarantine_directory=tmp_path / "q"
    )

    Image.new("RGB", (10, 10), "red").save(directory / "small.jpg")

    report = execute_actions(actions, apply=True)

    assert report.processed == []
    assert "mudou" in report.failures[0].message
    assert (directory / "small.jpg").exists()


def test_star_clustering_does_not_chain(tmp_path):
    from photosieve.comparison.hybrid_detector import HybridComparison
    from photosieve.scanner import ImageInfo

    def info(name, width):
        return ImageInfo(
            path=str(tmp_path / name), filename=name, extension=".png",
            image_format="PNG", size_bytes=100, width=width, height=width,
            is_animated=False,
        )

    def pair(a, b, score):
        return HybridComparison(a, b, "HIGH_SIMILARITY", score, 1, 1.0, 1.0, False)

    a, b, c = info("a.png", 300), info("b.png", 200), info("c.png", 100)
    # A≈B e B≈C, mas A e C NÃO são semelhantes.
    comparisons = [pair(a, b, 0.95), pair(b, c, 0.95)]

    actions = plan_similar_actions(
        comparisons, tmp_path, quarantine_directory=tmp_path.parent / "q2"
    )

    # B vai para A; C não é removida por encadeamento (seu único par é com B).
    assert [(x.kept.filename, x.target.filename) for x in actions] == [("a.png", "b.png")]


def test_choose_best_quality_is_deterministic(library):
    _, result, _ = library

    assert choose_best_quality(result.images_found).filename in {"big.png", "unrelated.png"}
    assert (
        choose_best_quality(result.images_found).filename
        == choose_best_quality(list(reversed(result.images_found))).filename
    )


def test_crop_matches_are_never_planned(library, tmp_path):
    from dataclasses import replace

    directory, _, comparisons = library
    as_crop = [replace(c, is_crop_match=True) for c in comparisons]

    actions = plan_similar_actions(
        as_crop, directory, quarantine_directory=tmp_path / "q", minimum_score=0.0
    )

    assert actions == []
