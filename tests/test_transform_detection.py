import pytest
from PIL import Image

from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.hybrid_detector import find_hybrid_similarities
from photosieve.image_analyzer import TRANSFORMS, calculate_transform_phashes
from photosieve.scanner import ImageScanner
from tests.conftest import make_scene


def _scan(directory):
    return {i.filename: i for i in ImageScanner().scan(directory).images_found}


@pytest.fixture
def scenes(tmp_path):
    directory = tmp_path / "scenes"
    directory.mkdir()
    original = make_scene(directory / "orig.png", seed=3, size=(400, 300))
    original.transpose(Image.Transpose.ROTATE_90).save(directory / "rot90.png")
    original.transpose(Image.Transpose.ROTATE_180).save(directory / "rot180.png")
    original.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(directory / "mirror.png")
    make_scene(directory / "other.png", seed=77, size=(400, 300))
    return _scan(directory)


def test_transform_hash_count(scenes, tmp_path):
    hashes = calculate_transform_phashes(scenes["orig.png"].path)

    assert len(hashes) == len(TRANSFORMS)


@pytest.mark.parametrize("name", ["rot90.png", "rot180.png", "mirror.png"])
def test_transformed_copy_found_only_with_flag(scenes, name):
    pair = [scenes["orig.png"], scenes[name]]

    without = find_hybrid_similarities(pair, phash_threshold=4)
    with_flag = find_hybrid_similarities(
        pair, phash_threshold=4, detect_transforms=True
    )

    assert without == []
    assert len(with_flag) == 1
    assert with_flag[0].is_transform_match
    assert with_flag[0].transform_distance <= 4


def test_rotation_by_90_does_not_penalize_aspect_ratio(scenes):
    comparisons = find_hybrid_similarities(
        [scenes["orig.png"], scenes["rot90.png"]],
        phash_threshold=4,
        detect_transforms=True,
    )

    assert comparisons[0].metadata_similarity == 1.0


def test_unrelated_image_is_not_a_transform_match(scenes):
    comparisons = find_hybrid_similarities(
        [scenes["orig.png"], scenes["other.png"]],
        phash_threshold=12,
        detect_transforms=True,
        cache=ImageAnalysisCache(),
    )

    assert not any(c.is_transform_match for c in comparisons)
