
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
        ],
    )

    import photosieve.main as cli

    captured = {}

    def fake_run_analyze(directory, phash_threshold, minimum_score):
        captured["directory"] = directory
        captured["phash_threshold"] = phash_threshold
        captured["minimum_score"] = minimum_score

    monkeypatch.setattr(cli, "run_analyze", fake_run_analyze)

    main()

    assert str(captured["directory"]) == "/tmp"
    assert captured["phash_threshold"] == 10
    assert captured["minimum_score"] == 0.80
