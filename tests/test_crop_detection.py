from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.hybrid_detector import compare_images, find_hybrid_similarities
from photosieve.image_analyzer import CROP_SCALES, CROP_WINDOW_POSITIONS, calculate_window_phashes
from photosieve.scanner import ImageScanner
from tests.conftest import make_scene


def _scan(directory):
    return {i.filename: i for i in ImageScanner().scan(directory).images_found}


def _setup(tmp_path):
    directory = tmp_path / "scenes"
    directory.mkdir()
    original = make_scene(directory / "orig.png", seed=1)
    # Recorte de 75% do lado, fora do centro e com a proporção preservada.
    original.crop((75, 75, 375, 375)).save(directory / "crop.png")
    make_scene(directory / "other.png", seed=999)
    return directory


def test_window_hash_count(tmp_path):
    directory = _setup(tmp_path)

    hashes = calculate_window_phashes(directory / "orig.png")

    assert len(hashes) == len(CROP_SCALES) * CROP_WINDOW_POSITIONS**2


def test_crop_is_found_only_with_detect_crops(tmp_path):
    images = _scan(_setup(tmp_path))
    pair = [images["orig.png"], images["crop.png"]]

    without = find_hybrid_similarities(pair, phash_threshold=4)
    with_crops = find_hybrid_similarities(pair, phash_threshold=4, detect_crops=True)

    assert without == []
    assert len(with_crops) == 1
    assert with_crops[0].is_crop_match
    assert with_crops[0].crop_distance <= 8


def test_unrelated_image_is_not_a_crop_match(tmp_path):
    images = _scan(_setup(tmp_path))

    comparison = compare_images(
        images["orig.png"],
        images["other.png"],
        cache=ImageAnalysisCache(),
        detect_crops=True,
    )

    assert not comparison.is_crop_match
    assert comparison.similarity_score < 0.70


def test_crop_fields_default_when_disabled(tmp_path):
    images = _scan(_setup(tmp_path))

    comparison = compare_images(images["orig.png"], images["crop.png"])

    assert comparison.crop_distance is None
    assert not comparison.is_crop_match


def test_invalid_crop_threshold_is_rejected(tmp_path):
    import pytest

    images = list(_scan(_setup(tmp_path)).values())

    with pytest.raises(ValueError):
        find_hybrid_similarities(images, detect_crops=True, crop_threshold=65)
