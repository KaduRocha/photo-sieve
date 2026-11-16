import pytest

from photosieve.duplicate_detector import find_exact_duplicates
from photosieve.file_manager import (
    ActionKind,
    choose_image_to_keep,
    execute_actions,
    plan_duplicate_actions,
)
from photosieve.scanner import ImageScanner


@pytest.fixture
def scanned(photo_dir):
    result = ImageScanner().scan(photo_dir)
    return result, find_exact_duplicates(result.images_found)


def test_keeps_shortest_path(scanned):
    _, groups = scanned

    assert choose_image_to_keep(groups[0]).filename == "a.png"


def test_plan_never_includes_kept_file(scanned, tmp_path):
    result, groups = scanned

    actions = plan_duplicate_actions(
        groups, result.root_directory, quarantine_directory=tmp_path / "q"
    )

    assert [a.target.filename for a in actions] == ["a_copy.png"]
    assert actions[0].kept.filename == "a.png"
    assert actions[0].destination == tmp_path / "q" / "a_copy.png"


def test_plan_rejects_quarantine_inside_root(scanned):
    result, groups = scanned

    with pytest.raises(ValueError):
        plan_duplicate_actions(
            groups,
            result.root_directory,
            quarantine_directory=result.root_directory + "/q",
        )


def test_dry_run_changes_nothing(scanned, tmp_path):
    result, groups = scanned
    actions = plan_duplicate_actions(
        groups, result.root_directory, quarantine_directory=tmp_path / "q"
    )

    report = execute_actions(actions, apply=False)

    assert not report.applied
    assert report.processed == []
    assert report.bytes_affected == actions[0].target.size_bytes
    assert not (tmp_path / "q").exists()


def test_apply_move_and_delete(scanned, tmp_path):
    result, groups = scanned
    actions = plan_duplicate_actions(
        groups, result.root_directory, quarantine_directory=tmp_path / "q"
    )

    report = execute_actions(actions, apply=True)

    assert len(report.processed) == 1
    assert (tmp_path / "q" / "a_copy.png").exists()

    delete_actions = plan_duplicate_actions(
        groups, result.root_directory, kind=ActionKind.DELETE
    )
    # a_copy já foi movida: a ação vira falha registrada, sem exceção.
    failed = execute_actions(delete_actions, kind=ActionKind.DELETE, apply=True)

    assert len(failed.failures) == 1


def test_apply_skips_when_file_changed(scanned, tmp_path):
    result, groups = scanned
    actions = plan_duplicate_actions(
        groups, result.root_directory, quarantine_directory=tmp_path / "q"
    )

    # Altera a cópia depois do planejamento: não pode mais ser movida.
    target = actions[0].target.path
    with open(target, "ab") as file:
        file.write(b"changed")

    report = execute_actions(actions, apply=True)

    assert report.processed == []
    assert "idênticos" in report.failures[0].message
    assert not (tmp_path / "q").exists()


def test_apply_refuses_to_overwrite_destination(scanned, tmp_path):
    result, groups = scanned
    quarantine = tmp_path / "q"
    quarantine.mkdir()
    (quarantine / "a_copy.png").write_bytes(b"existing")

    actions = plan_duplicate_actions(
        groups, result.root_directory, quarantine_directory=quarantine
    )
    report = execute_actions(actions, apply=True)

    assert len(report.failures) == 1
    assert (quarantine / "a_copy.png").read_bytes() == b"existing"
