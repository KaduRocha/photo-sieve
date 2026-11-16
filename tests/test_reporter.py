from pathlib import Path

from photosieve import reporter
from photosieve.duplicate_detector import find_exact_duplicates
from photosieve.scanner import ImageScanner


def test_format_size_units():
    assert reporter.format_size(0) == "0.00 B"
    assert reporter.format_size(1024) == "1.00 KB"
    assert reporter.format_size(1024**2) == "1.00 MB"
    assert reporter.format_size(1024**5) == "1.00 PB"


def test_relative_path():
    assert reporter.relative_path("/a/b/c.png", "/a") == Path("b/c.png")


def test_print_duplicate_group_with_and_without_sha(photo_dir, capsys):
    result = ImageScanner().scan(photo_dir)
    group = find_exact_duplicates(result.images_found)[0]

    reporter.print_duplicate_group(1, group, result.root_directory)
    with_sha = capsys.readouterr().out

    reporter.print_duplicate_group(
        1, group, result.root_directory, show_sha256=False
    )
    without_sha = capsys.readouterr().out

    assert "SHA-256:" in with_sha
    assert "SHA-256:" not in without_sha
    assert "a.png" in with_sha and "a_copy.png" in with_sha


def test_print_scan_errors(photo_dir, capsys):
    result = ImageScanner().scan(photo_dir)

    reporter.print_scan_errors(result)

    assert "broken.jpg" in capsys.readouterr().out
