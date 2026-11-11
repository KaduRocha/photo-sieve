import pytest

from photosieve import main as cli


def test_run_scan_lists_images(photo_dir, capsys):
    cli.run_scan(photo_dir)
    out = capsys.readouterr().out

    assert "Valid images: 3" in out
    assert "Invalid images: 1" in out
    assert "a.png" in out
    assert "Scan completed." in out


def test_run_scan_missing_directory(tmp_path, capsys):
    cli.run_scan(tmp_path / "nope")

    assert "Error:" in capsys.readouterr().out


def test_run_duplicates_reports_group(photo_dir, capsys):
    cli.run_duplicates(photo_dir)
    out = capsys.readouterr().out

    assert "Duplicate groups: 1" in out
    assert "Duplicate files: 1" in out
    assert "No files were modified or deleted." in out


def test_run_duplicates_none(tmp_path, capsys):
    from tests.conftest import make_image

    make_image(tmp_path / "x.png", "red")
    make_image(tmp_path / "y.png", "blue", stripe="white")

    cli.run_duplicates(tmp_path)

    assert "No exact duplicates found." in capsys.readouterr().out


def test_run_similar_groups_identical_images(photo_dir, capsys):
    cli.run_similar(photo_dir, threshold=6)
    out = capsys.readouterr().out

    assert "Similarity groups: 1" in out
    assert "Perceptually identical" in out


def test_run_similar_invalid_threshold_is_reported(photo_dir, capsys):
    cli.run_similar(photo_dir, threshold=99)

    assert "Error:" in capsys.readouterr().out


def test_run_analyze_full_report(photo_dir, capsys):
    cli.run_analyze(photo_dir, phash_threshold=12, minimum_score=0.7, workers=2)
    out = capsys.readouterr().out

    assert "Exact duplicate groups: 1" in out
    assert "EXACT DUPLICATES" in out
    assert "SCAN ERRORS" in out
    assert "Hybrid analysis completed." in out


def test_run_analyze_requires_two_images(tmp_path, capsys):
    from tests.conftest import make_image

    make_image(tmp_path / "only.png")

    cli.run_analyze(tmp_path, 12, 0.7, 1)

    assert "At least two valid images" in capsys.readouterr().out


def test_analyze_shares_sha256_cache(photo_dir, monkeypatch):
    """Cada arquivo deve ter o SHA-256 calculado no máximo uma vez."""
    import photosieve.comparison.analysis_cache as cache_module

    calls = []
    original = cache_module.calculate_sha256

    def counting(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(cache_module, "calculate_sha256", counting)

    cli.run_analyze(photo_dir, 12, 0.7, 1)

    assert len(calls) == len(set(calls))


@pytest.mark.parametrize(
    "argv",
    [
        ["analyze", "x", "--workers", "0"],
        ["analyze", "x", "--phash-threshold", "65"],
        ["analyze", "x", "--minimum-score", "1.5"],
        ["similar", "x", "--threshold", "-1"],
    ],
)
def test_cli_rejects_out_of_range_values(argv, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["photosieve", *argv])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "fora do intervalo" in capsys.readouterr().err


def test_dedupe_dry_run_does_not_touch_files(photo_dir, tmp_path, capsys):
    cli.run_dedupe(photo_dir)
    out = capsys.readouterr().out

    assert "DRY-RUN" in out
    assert (photo_dir / "a.png").exists()
    assert (photo_dir / "a_copy.png").exists()
    assert not (tmp_path / "photos_photosieve_duplicates").exists()


def test_dedupe_apply_moves_to_quarantine(photo_dir, tmp_path, capsys):
    cli.run_dedupe(photo_dir, apply=True)

    quarantine = tmp_path / "photos_photosieve_duplicates"

    assert (photo_dir / "a.png").exists()
    assert not (photo_dir / "a_copy.png").exists()
    assert (quarantine / "a_copy.png").exists()
    assert "Files processed: 1" in capsys.readouterr().out


def test_dedupe_delete_requires_confirmation(photo_dir, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "n")

    cli.run_dedupe(photo_dir, delete=True, apply=True)

    assert (photo_dir / "a_copy.png").exists()
    assert "Cancelled" in capsys.readouterr().out


def test_dedupe_delete_with_yes(photo_dir):
    cli.run_dedupe(photo_dir, delete=True, apply=True, assume_yes=True)

    assert (photo_dir / "a.png").exists()
    assert not (photo_dir / "a_copy.png").exists()


def test_analyze_writes_report_and_validates_extension(photo_dir, tmp_path, capsys):
    report = tmp_path / "out" / "r.html"

    cli.run_analyze(photo_dir, 12, 0.7, 1, report_path=report)

    assert report.exists()
    assert "Report written" in capsys.readouterr().out

    cli.run_analyze(photo_dir, 12, 0.7, 1, report_path=tmp_path / "r.pdf")
    out = capsys.readouterr().out

    assert "Formato de relatório não suportado" in out
    assert "HYBRID ANALYSIS" not in out  # falhou cedo, antes de analisar


def test_analyze_uses_persistent_cache(photo_dir, tmp_path):
    db = tmp_path / "cache" / "c.db"

    cli.run_analyze(photo_dir, 12, 0.7, 1, cache_path=db)

    assert db.exists()

    from photosieve.comparison.persistent_store import PersistentStore

    with PersistentStore(db) as store:
        assert store.count() > 0


def test_analyze_with_crop_detection_runs(photo_dir, capsys):
    cli.run_analyze(photo_dir, 12, 0.7, 1, detect_crops=True)

    assert "Crop detection: on" in capsys.readouterr().out


def test_dedupe_similar_dry_run_and_apply(tmp_path, capsys):
    from tests.conftest import make_scene

    directory = tmp_path / "lib"
    directory.mkdir()
    big = make_scene(directory / "big.png", seed=3, size=(400, 400))
    big.resize((200, 200)).save(directory / "small.jpg", quality=80)

    cli.run_dedupe(directory, similar=True)
    out = capsys.readouterr().out

    assert "% similar" in out
    assert (directory / "small.jpg").exists()

    cli.run_dedupe(directory, similar=True, apply=True)

    assert not (directory / "small.jpg").exists()
    assert (tmp_path / "lib_photosieve_duplicates" / "small.jpg").exists()
    assert (directory / "big.png").exists()


def test_dedupe_similar_refuses_delete(photo_dir, capsys):
    cli.run_dedupe(photo_dir, similar=True, delete=True, apply=True, assume_yes=True)

    assert "--delete não pode ser usado com --similar" in capsys.readouterr().out
    assert (photo_dir / "a_copy.png").exists()


def test_main_wires_new_options(monkeypatch, tmp_path):
    captured = {}

    monkeypatch.setattr(cli, "run_analyze", lambda *a, **k: captured.update(k))
    monkeypatch.setattr(
        "sys.argv",
        ["photosieve", "analyze", "/tmp", "--report", "r.json", "--detect-crops",
         "--crop-threshold", "5", "--no-cache"],
    )
    cli.main()

    assert captured["cache_path"] is None
    assert str(captured["report_path"]) == "r.json"
    assert captured["detect_crops"] is True
    assert captured["crop_threshold"] == 5

    monkeypatch.setattr("sys.argv", ["photosieve", "analyze", "/tmp", "--cache-db", str(tmp_path / "x.db")])
    cli.main()

    assert captured["cache_path"] == tmp_path / "x.db"
