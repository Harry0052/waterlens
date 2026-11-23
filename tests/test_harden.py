import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from waterlens.cli import main
from waterlens.errors import WaterLensError
from waterlens.models import Reading
from waterlens.score import household_day_status
from waterlens.workflow import prepare_output, run_demo, write_inside

ROOT = Path(__file__).resolve().parents[1]


def test_demo_stays_inside_the_output_budget(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    started = time.perf_counter()
    first = run_demo(output)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0
    second = run_demo(output)
    assert first["detectors"]["persistence"]["precision"] == second["detectors"]["persistence"]["precision"]
    assert first["detectors"]["persistence"]["recall"] == second["detectors"]["persistence"]["recall"]
    assert first["detectors"]["persistence"]["median_delay_minutes"] == 15
    assert (output / "score.json").is_file()
    assert (output / "report.html").is_file()


def test_generated_names_cannot_escape_the_output_directory(tmp_path: Path) -> None:
    root = prepare_output(tmp_path / "out")
    try:
        write_inside(root, "../escape.txt", "nope")
    except WaterLensError as exc:
        assert exc.category == "io"
        assert "outside" in str(exc)
    else:
        raise AssertionError("expected a path escape to be rejected")
    assert not (tmp_path / "escape.txt").exists()


def test_sparse_household_day_is_excluded() -> None:
    start = datetime(2026, 6, 15, 7, 0, tzinfo=timezone.utc)
    readings = []
    for index in range(10):
        moment = start + timedelta(minutes=5 * index)
        readings.append(
            Reading("HH", moment, moment + timedelta(minutes=5), 300, 0.0, "generated", index, f"t{index}")
        )
    eligible, excluded = household_day_status(readings, ["HH"], {"HH": "UTC"})
    assert eligible == 0
    assert excluded[0]["reason"] == "insufficient_coverage"
    assert excluded[0]["observed_intervals"] == 10


def test_exported_alarm_file_scores_without_being_executed(tmp_path: Path) -> None:
    demo = tmp_path / "demo"
    run_demo(demo)
    output = tmp_path / "external"
    assert main(
        [
            "score",
            "--fixture",
            str(demo / "fixtures" / "heldout"),
            "--alarms",
            str(demo / "alarms_persistence.csv"),
            "--output",
            str(output),
        ]
    ) == 0
    report = json.loads((output / "score.json").read_text(encoding="utf-8"))
    assert report["precision"] == 0.5
    assert report["recall"] == 0.5
    assert report["median_delay_minutes"] == 15
    assert report["alarm_file"].endswith("alarms_persistence.csv")
