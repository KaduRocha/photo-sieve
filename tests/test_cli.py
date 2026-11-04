
from pathlib import Path

from photosieve.main import main


def test_analyze_command_is_registered(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["photosieve", "analyze", "--help"],
    )

    try:
        main()
    except SystemExit as error:
        assert error.code == 0


def test_analyze_command_accepts_custom_parameters(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "photosieve",
            "analyze",
            "/tmp",
            "--phash-threshold",
            "10",
            "--minimum-score",
            "0.80",
            "--workers",
            "2",
        ],
    )

    import photosieve.main as cli

    captured = {}

    def fake_run_analyze(
        directory,
        phash_threshold,
        minimum_score,
        workers,
    ):
        captured["directory"] = directory
        captured["phash_threshold"] = phash_threshold
        captured["minimum_score"] = minimum_score
        captured["workers"] = workers

    monkeypatch.setattr(cli, "run_analyze", fake_run_analyze)

    cli.main()

    assert captured["directory"] == Path("/tmp")
    assert captured["phash_threshold"] == 10
    assert captured["minimum_score"] == 0.80
    assert captured["workers"] == 2

def test_analyze_command_uses_default_workers(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        [
            "photosieve",
            "analyze",
            "/tmp",
        ],
    )

    import photosieve.main as cli

    captured = {}

    def fake_run_analyze(
        directory,
        phash_threshold,
        minimum_score,
        workers,
    ):
        captured["workers"] = workers

    monkeypatch.setattr(cli, "run_analyze", fake_run_analyze)

    cli.main()

    assert captured["workers"] == 4