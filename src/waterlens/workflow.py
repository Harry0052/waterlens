"""User-facing demo and external-alarm scoring. Both call the same scorer."""

from __future__ import annotations

import json
from pathlib import Path

from waterlens import __version__
from waterlens.detectors import predict
from waterlens.errors import WaterLensError
from waterlens.fixtures import HELDOUT, TRAIN, write_schedule
from waterlens.models import REPORT_SCHEMA
from waterlens.parse import load_fixture, parse_alarms
from waterlens.report import alarm_csv, build_timeline, comparison_summary, render_html, timeline_csv
from waterlens.score import LIMITATIONS, score_alarms, tune


def prepare_output(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.exists() and not resolved.is_dir():
        raise WaterLensError("io", f"output path is not a directory: {resolved}", path=str(resolved))
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def write_inside(root: Path, relative: str, text: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or any(part in {"..", ""} for part in rel.parts):
        raise WaterLensError("io", f"refusing to write outside the output directory: {relative}")
    target = (root / rel).resolve()
    if root.resolve() not in target.parents:
        raise WaterLensError("io", f"refusing to write outside the output directory: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def _zones(fixture, household_ids: list[str]) -> dict[str, str]:
    return {household_id: fixture.timezone_for(household_id) for household_id in household_ids}


def _section(train, test, detector_id: str) -> tuple[dict, list]:
    train_ids = train.split_households("train")
    test_ids = test.split_households("test")
    params = tune(train.readings, train.events, train_ids, detector_id, _zones(train, train_ids))
    alarms = predict(test.readings, params, test_ids)
    report = score_alarms(
        test.readings,
        test.events,
        alarms,
        test_ids,
        _zones(test, test_ids),
        parameters=params,
        source_readings=str(Path(test.readings_path).resolve()),
        missing=[item for item in test.missing_intervals if item["household_id"] in set(test_ids)],
        config_hashes={item.id: item.config_hash for item in list(train.configurations) + list(test.configurations)},
        train_households=train_ids,
    )
    return report, alarms


def run_demo(output: Path) -> dict:
    root = prepare_output(output)
    train_dir = root / "fixtures" / "train"
    test_dir = root / "fixtures" / "heldout"
    write_schedule(train_dir, TRAIN)
    write_schedule(test_dir, HELDOUT)
    train = load_fixture(train_dir)
    test = load_fixture(test_dir)
    persistence, persistence_alarms = _section(train, test, "persistence")
    threshold, threshold_alarms = _section(train, test, "threshold")
    hashes = {}
    hashes.update(persistence["config_hashes"])
    comparison = {
        "schema_version": REPORT_SCHEMA,
        "software_version": __version__,
        "generated": True,
        "units": persistence["units"],
        "train_households": persistence["train_households"],
        "test_households": persistence["test_households"],
        "config_hashes": hashes,
        "limitations": list(LIMITATIONS),
        "detectors": {"persistence": persistence, "threshold": threshold},
    }
    zones = _zones(test, test.split_households("test"))
    timeline = build_timeline(test, persistence_alarms + threshold_alarms)
    write_inside(root, "score.json", json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    write_inside(root, "summary.txt", comparison_summary(comparison))
    write_inside(root, "report.html", render_html(comparison, timeline))
    write_inside(root, "timeline.csv", timeline_csv(timeline))
    write_inside(root, "alarms_persistence.csv", alarm_csv(persistence_alarms, zones))
    write_inside(root, "alarms_threshold.csv", alarm_csv(threshold_alarms, zones))
    return comparison


def score_external(fixture_dir: Path, alarms_path: Path, output: Path) -> dict:
    root = prepare_output(output)
    fixture = load_fixture(fixture_dir)
    alarms = parse_alarms(alarms_path, fixture.readings)
    household_ids = fixture.split_households("test") or sorted({item.household_id for item in fixture.readings})
    report = score_alarms(
        fixture.readings,
        fixture.events,
        alarms,
        household_ids,
        _zones(fixture, household_ids),
        parameters=None,
        source_readings=str(Path(fixture.readings_path).resolve()),
        missing=[item for item in fixture.missing_intervals if item["household_id"] in set(household_ids)],
        config_hashes={item.id: item.config_hash for item in fixture.configurations},
        train_households=[],
    )
    report["alarm_file"] = str(alarms_path)
    write_inside(root, "score.json", json.dumps(report, indent=2, sort_keys=True) + "\n")
    write_inside(root, "summary.txt", comparison_summary({
        "train_households": [],
        "test_households": household_ids,
        "config_hashes": report["config_hashes"],
        "limitations": report["limitations"],
        "detectors": {report["detector_id"]: report},
    }))
    return report
