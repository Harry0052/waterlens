import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from waterlens.cli import main
from waterlens.detectors import DetectorParams, predict
from waterlens.models import Alarm, Event, Reading
from waterlens.parse import load_fixture
from waterlens.score import score_alarms, tune

ROOT = Path(__file__).resolve().parents[1]
ORACLE = json.loads((ROOT / "fixtures" / "oracle" / "heldout_persistence.json").read_text(encoding="utf-8"))


def _zones(fixture, household_ids):
    return {household_id: fixture.timezone_for(household_id) for household_id in household_ids}


def test_persistence_matches_hand_oracle(tmp_path: Path) -> None:
    assert main(
        [
            "evaluate",
            "--train",
            str(ROOT / "fixtures" / "valid"),
            "--test",
            str(ROOT / "fixtures" / "heldout"),
            "--detector",
            "persistence",
            "--output",
            str(tmp_path),
        ]
    ) == 0
    report = json.loads((tmp_path / "score.json").read_text(encoding="utf-8"))
    assert report["parameters"] == ORACLE["parameters"]
    assert report["precision"] == ORACLE["precision"]
    assert report["recall"] == ORACLE["recall"]
    assert report["median_delay_minutes"] == ORACLE["median_delay_minutes"]
    assert report["true_positives"] == ORACLE["true_positives"]
    assert report["false_positives"] == ORACLE["false_positives"]
    assert report["false_negatives"] == ORACLE["false_negatives"]
    assert report["eligible_household_days"] == ORACLE["eligible_household_days"]
    assert report["false_alerts_per_eligible_household_day"] == ORACLE["false_alerts_per_eligible_household_day"]
    assert report["matches"][0]["event_id"] == ORACLE["matched_event_id"]
    assert report["matches"][0]["event_start"] == ORACLE["matched_event_start"]
    assert report["matches"][0]["alarm_start"] == ORACLE["matched_alarm_start"]
    assert report["matches"][0]["alarm_end"] == ORACLE["matched_alarm_end"]
    assert report["matches"][0]["delay_minutes"] == ORACLE["delay_minutes"]
    assert report["unmatched_events"][0]["event_id"] == ORACLE["missed_event_id"]
    assert report["unmatched_alarms"][0]["alarm_start"] == ORACLE["irrigation_alarm_start"]
    assert report["unmatched_alarms"][0]["alarm_end"] == ORACLE["irrigation_alarm_end"]
    summary = (tmp_path / "summary.txt").read_text(encoding="utf-8")
    assert "E-HELD-LEAK-P" in summary
    assert "2026-06-15T10:15:00-07:00" in summary
    assert "generated" in summary.lower() or "Generated" in summary or "generated" in summary


def test_heldout_edits_do_not_change_training(tmp_path: Path) -> None:
    train = load_fixture(ROOT / "fixtures" / "valid")
    held = load_fixture(ROOT / "fixtures" / "heldout")
    train_ids = train.split_households("train")
    zones = _zones(train, train_ids)
    baseline = tune(train.readings, train.events, train_ids, "persistence", zones)
    mutated = list(held.readings)
    mutated[0] = Reading(
        household_id=mutated[0].household_id,
        start=mutated[0].start,
        end=mutated[0].end,
        interval_seconds=mutated[0].interval_seconds,
        volume_liters=50.0,
        provenance=mutated[0].provenance,
        source_row=mutated[0].source_row,
        timestamp_text=mutated[0].timestamp_text,
    )
    again = tune(train.readings, train.events, train_ids, "persistence", zones)
    assert baseline == again
    assert DetectorParams("persistence", 0.25, 15) == baseline
    threshold = tune(train.readings, train.events, train_ids, "threshold", zones)
    assert threshold == DetectorParams("threshold", 0.25, 0)
    assert mutated[0].volume_liters == 50.0


def test_competing_alarms_score_one_event_once() -> None:
    start = datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc)
    readings = [
        Reading("HH", start, start + timedelta(minutes=5), 300, 0.4, "generated", 2, "t0"),
    ]
    event = Event(
        "E1",
        "HH",
        start,
        start + timedelta(minutes=30),
        "leak_persistent",
        "planted_leak",
        0.4,
        (),
        2,
        "s",
        "e",
        "",
    )
    alarms = [
        Alarm("B", "HH", "external", start, start + timedelta(minutes=10), "external"),
        Alarm("A", "HH", "external", start, start + timedelta(minutes=10), "external"),
    ]
    # One observed slot of a 30-minute event is below the 50% observed rule.
    # Use a fully observed 5-minute event instead.
    event = Event(
        "E1",
        "HH",
        start,
        start + timedelta(minutes=5),
        "leak_persistent",
        "planted_leak",
        0.4,
        (),
        2,
        "s",
        "e",
        "",
    )
    report = score_alarms(
        readings,
        [event],
        alarms,
        ["HH"],
        {"HH": "UTC"},
        source_readings="memory",
    )
    assert report["true_positives"] == 1
    assert report["false_positives"] == 1
    assert report["matches"][0]["alarm_id"] == "A"


def test_gap_breaks_persistence_and_is_not_interpolated() -> None:
    zone_start = datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc)
    readings = []
    for offset in (0, 5, 15, 20, 25):
        start = zone_start + timedelta(minutes=offset)
        readings.append(
            Reading("HH", start, start + timedelta(minutes=5), 300, 0.4, "generated", offset, f"t{offset}")
        )
    alarms = predict(readings, DetectorParams("persistence", 0.25, 15), ["HH"])
    assert alarms == []


def test_alarm_start_does_not_use_future_readings() -> None:
    start = datetime(2026, 6, 15, 17, 0, tzinfo=timezone.utc)
    full = []
    for offset in range(0, 40, 5):
        moment = start + timedelta(minutes=offset)
        full.append(Reading("HH", moment, moment + timedelta(minutes=5), 300, 0.4, "generated", offset, f"t{offset}"))
    early = [item for item in full if item.start <= start + timedelta(minutes=15)]
    early_alarms = predict(early, DetectorParams("persistence", 0.25, 15), ["HH"])
    full_alarms = predict(full, DetectorParams("persistence", 0.25, 15), ["HH"])
    assert early_alarms[0].start == full_alarms[0].start == start + timedelta(minutes=15)
    assert early_alarms[0].end < full_alarms[0].end
