import json
from datetime import timezone
from pathlib import Path

from waterlens.cli import main
from waterlens.fixtures import TRAIN, configuration_record, fold_configuration_record, write_invalid_bundle, write_valid_bundle
from waterlens.hashutil import config_hash
from waterlens.parse import load_fixture, parse_readings

ROOT = Path(__file__).resolve().parents[1]
VALID = ROOT / "fixtures" / "valid"
INVALID = ROOT / "fixtures" / "invalid"


def test_committed_valid_fixture_matches_generator(tmp_path: Path) -> None:
    write_valid_bundle(tmp_path)
    for name in ("readings.csv", "events.csv", "manifest.json"):
        assert (tmp_path / name).read_text(encoding="utf-8") == (VALID / name).read_text(encoding="utf-8")


def test_valid_fixture_accepts_and_reports_artifacts() -> None:
    loaded = load_fixture(VALID)
    assert loaded.duplicates_ignored == 2
    assert loaded.conflicts == []
    assert len(loaded.missing_intervals) == 1
    hashes = {item.id: item.config_hash for item in loaded.configurations}
    assert hashes["train"] == configuration_record(TRAIN)["config_hash"]
    assert hashes["fold"] == fold_configuration_record()["config_hash"]
    assert hashes["train"] == config_hash(configuration_record(TRAIN))
    fold = [item for item in loaded.readings if item.household_id == "HH-FOLD-01"]
    assert [item.start for item in fold] == sorted(item.start for item in fold)
    assert fold[0].timestamp_text == "2026-11-01T01:55:00-04:00"
    assert fold[1].timestamp_text == "2026-11-01T01:00:00-05:00"
    assert fold[0].start.astimezone(timezone.utc) < fold[1].start.astimezone(timezone.utc)
    first_line = VALID.joinpath("readings.csv").read_text(encoding="utf-8").splitlines()[1]
    assert first_line.startswith("HH-TRAIN-01,2026-06-14T23:55:00-07:00")


def test_cli_accepts_valid_fixture(capsys) -> None:
    assert main(["validate", str(VALID)]) == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["duplicates_ignored"] == 2
    assert payload["missing_intervals"] == 1
    assert "exact duplicates ignored" in captured.err


def test_cli_rejects_negative_volume(capsys) -> None:
    assert main(["validate", str(INVALID)]) == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["status"] == "error"
    assert payload["category"] == "value"
    assert "volume_liters" in payload["message"]
    assert "-1" in payload["message"]
    assert payload["row"] is not None
    assert "volume_liters" in captured.err


def test_conflicting_duplicate_is_quarantined(tmp_path: Path) -> None:
    write_valid_bundle(tmp_path)
    readings = (tmp_path / "readings.csv").read_text(encoding="utf-8")
    readings += "HH-FOLD-01,2026-11-01T01:05:00-05:00,300,1.5000,generated\n"
    (tmp_path / "readings.csv").write_text(readings, encoding="utf-8")
    loaded = load_fixture(tmp_path)
    assert len(loaded.conflicts) == 1
    assert loaded.conflicts[0].household_id == "HH-FOLD-01"
    assert all(item.timestamp_text != "2026-11-01T01:05:00-05:00" for item in loaded.readings if item.household_id == "HH-FOLD-01")


def test_row_bound(tmp_path: Path) -> None:
    write_valid_bundle(tmp_path)
    try:
        parse_readings(tmp_path / "readings.csv", max_rows=3)
    except Exception as exc:
        assert "row limit" in str(exc)
    else:
        raise AssertionError("expected a row-limit error")


def test_invalid_bundle_generator_matches_commit(tmp_path: Path) -> None:
    write_invalid_bundle(tmp_path)
    for name in ("readings.csv", "events.csv", "manifest.json"):
        assert (tmp_path / name).read_text(encoding="utf-8") == (INVALID / name).read_text(encoding="utf-8")
