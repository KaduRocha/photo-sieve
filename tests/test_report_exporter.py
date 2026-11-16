import csv
import io

import pytest

from photosieve.comparison.hybrid_detector import find_hybrid_similarities
from photosieve.duplicate_detector import find_exact_duplicates
from photosieve.report_exporter import (
    AnalysisReport,
    build_csv,
    build_html,
    build_json_data,
    validate_report_path,
    write_report,
)
from photosieve.scanner import ImageScanner
from tests.conftest import make_image


def _report(directory):
    result = ImageScanner().scan(directory)

    return AnalysisReport(
        root_directory=result.root_directory,
        parameters={"phash_threshold": 12},
        scan=result,
        duplicate_groups=find_exact_duplicates(result.images_found),
        comparisons=find_hybrid_similarities(result.images_found),
    )


def test_json_structure(photo_dir):
    data = build_json_data(_report(photo_dir))

    assert data["summary"]["images"] == 3
    assert data["summary"]["exact_duplicate_groups"] == 1
    assert len(data["exact_duplicates"][0]["files"]) == 2
    assert data["errors"][0]["path"].endswith("broken.jpg")
    assert all(not f["path"].startswith("/") for f in data["exact_duplicates"][0]["files"])


def test_csv_has_header_and_rows(photo_dir):
    rows = list(csv.reader(io.StringIO(build_csv(_report(photo_dir)))))

    assert rows[0][0] == "kind"
    assert rows[1][0] == "exact_duplicate"
    assert rows[1][-1] == "a.png"  # mantém o caminho mais curto


def test_csv_neutralizes_formula_injection(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    make_image(directory / "=cmd.png", "red", stripe="blue")
    make_image(directory / "+x.png", "red", stripe="blue")

    text = build_csv(_report(directory))

    assert "'=cmd.png" in text
    assert ",=cmd.png" not in text


def test_html_escapes_filenames_and_embeds_thumbnails(tmp_path):
    directory = tmp_path / "p"
    directory.mkdir()
    make_image(directory / "a<img src=x onerror=alert(1)>.png", "red", stripe="blue")
    make_image(directory / "copy.png", "red", stripe="blue")

    page = build_html(_report(directory))

    assert "<img src=x onerror" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert "data:image/jpeg;base64," in page


@pytest.mark.parametrize("name", ["r.json", "r.csv", "r.html"])
def test_write_report_formats(photo_dir, tmp_path, name):
    path = write_report(_report(photo_dir), tmp_path / "out" / name)

    assert path.exists() and path.stat().st_size > 0


def test_unsupported_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        validate_report_path(tmp_path / "r.pdf")
