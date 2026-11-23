"""Command line entry point. Machine output goes to stdout; notes go to stderr."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from waterlens.detectors import predict
from waterlens.errors import WaterLensError
from waterlens.parse import load_fixture
from waterlens.score import score_alarms, tune
from waterlens.workflow import run_demo, score_external


def _emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _fail(error: WaterLensError) -> int:
    print(str(error), file=sys.stderr)
    _emit(error.as_dict())
    return 2


def validate_command(fixture: Path) -> int:
    loaded = load_fixture(fixture)
    print(
        f"validated {fixture}: {len(loaded.readings)} readings, "
        f"{loaded.duplicates_ignored} exact duplicates ignored, "
        f"{len(loaded.conflicts)} conflicting timestamps quarantined, "
        f"{len(loaded.missing_intervals)} missing intervals",
        file=sys.stderr,
    )
    _emit(
        {
            "status": "ok",
            "conflicts": [
                {
                    "household_id": item.household_id,
                    "reason": item.reason,
                    "rows": list(item.rows),
                    "timestamp": item.timestamp_text,
                }
                for item in loaded.conflicts
            ],
            "configurations": [
                {
                    "config_hash": item.config_hash,
                    "households": list(item.households),
                    "id": item.id,
                    "seed": item.seed,
                    "split": item.split,
                    "timezone": item.timezone,
                }
                for item in loaded.configurations
            ],
            "duplicates_ignored": loaded.duplicates_ignored,
            "events": len(loaded.events),
            "generated": True,
            "missing_intervals": len(loaded.missing_intervals),
            "readings": len(loaded.readings),
            "units": {"interval": "seconds", "volume": "liters"},
        }
    )
    return 0


def _zones(fixture, household_ids: list[str]) -> dict[str, str]:
    return {household_id: fixture.timezone_for(household_id) for household_id in household_ids}


def _summary(report: dict) -> str:
    lines = [
        "WaterLens score",
        "Measurements in this report are generated.",
        f"Detector: {report['detector_id']}",
        f"Parameters: {json.dumps(report['parameters'], sort_keys=True)}",
        f"Precision: {report['precision']}",
        f"Recall: {report['recall']}",
        f"Median delay (minutes): {report['median_delay_minutes']}",
        (
            "False alerts per eligible household-day: "
            f"{report['false_alerts_per_eligible_household_day']} "
            f"({report['false_alerts']} false alerts / {report['eligible_household_days']} eligible days)"
        ),
        "Matches:",
    ]
    for match in report["matches"]:
        lines.append(
            f"  {match['event_id']} {match['event_start']} -> {match['alarm_id']} "
            f"{match['alarm_start']} delay {match['delay_minutes']} minutes"
        )
    lines.append("Unmatched alarms:")
    for alarm in report["unmatched_alarms"]:
        lines.append(f"  {alarm['alarm_id']} {alarm['alarm_start']} to {alarm['alarm_end']}")
    lines.append("Unmatched planted events:")
    for event in report["unmatched_events"]:
        lines.append(f"  {event['event_id']} {event['event_start']} to {event['event_end']}")
    if report["excluded_household_days"]:
        lines.append("Excluded household-days:")
        for day in report["excluded_household_days"]:
            lines.append(f"  {day['household_id']} {day['date']} {day['reason']}")
    lines.append("Limitations:")
    lines.extend(f"  - {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def evaluate_command(train: Path, test: Path, detector: str, output: Path) -> int:
    if detector not in {"persistence", "threshold"}:
        raise WaterLensError("value", "detector must be persistence or threshold")
    train_fixture = load_fixture(train)
    test_fixture = load_fixture(test)
    train_ids = train_fixture.split_households("train")
    test_ids = test_fixture.split_households("test")
    if not train_ids:
        raise WaterLensError("value", "training fixture has no train split", path=str(train))
    if not test_ids:
        raise WaterLensError("value", "test fixture has no test split", path=str(test))
    params = tune(
        train_fixture.readings,
        train_fixture.events,
        train_ids,
        detector,
        _zones(train_fixture, train_ids),
    )
    alarms = predict(test_fixture.readings, params, test_ids)
    hashes = {item.id: item.config_hash for item in train_fixture.configurations}
    hashes.update({item.id: item.config_hash for item in test_fixture.configurations})
    report = score_alarms(
        test_fixture.readings,
        test_fixture.events,
        alarms,
        test_ids,
        _zones(test_fixture, test_ids),
        parameters=params,
        source_readings=test_fixture.readings_path,
        missing=[item for item in test_fixture.missing_intervals if item["household_id"] in set(test_ids)],
        config_hashes=hashes,
        train_households=train_ids,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "score.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "summary.txt").write_text(_summary(report), encoding="utf-8")
    print(f"wrote {output / 'score.json'}", file=sys.stderr)
    _emit(report)
    return 0


def demo_command(output: Path) -> int:
    report = run_demo(output)
    print(f"wrote {output / 'report.html'}", file=sys.stderr)
    print("Open report.html, then use summary.txt for the same figures in text.", file=sys.stderr)
    _emit(report)
    return 0


def score_command(fixture: Path, alarms: Path, output: Path) -> int:
    report = score_external(fixture, alarms, output)
    print(f"wrote {output / 'score.json'}", file=sys.stderr)
    _emit(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="waterlens",
        description=(
            "Score household water-leak detectors on generated interval traces. "
            "Measurements shipped with WaterLens are synthetic."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Accept a fixture directory or reject it with an actionable error")
    validate.add_argument("fixture", type=Path, help="Directory with manifest.json, readings.csv, and events.csv")
    evaluate = sub.add_parser("evaluate", help="Tune one baseline on the train split and score the test split")
    evaluate.add_argument("--train", required=True, type=Path, help="Training fixture directory")
    evaluate.add_argument("--test", required=True, type=Path, help="Held-out fixture directory")
    evaluate.add_argument("--detector", required=True, choices=["persistence", "threshold"])
    evaluate.add_argument("--output", required=True, type=Path, help="Directory for score.json and summary.txt")
    demo = sub.add_parser("demo", help="Generate the sample households, score both baselines, and write the report")
    demo.add_argument("--output", required=True, type=Path, help="Directory for the report, timeline, and fixtures")
    score = sub.add_parser("score", help="Score an alarm CSV. The file is validated and is not executed.")
    score.add_argument("--fixture", required=True, type=Path, help="Fixture directory with readings, events, and manifest")
    score.add_argument("--alarms", required=True, type=Path, help="Predicted alarm intervals")
    score.add_argument("--output", required=True, type=Path, help="Directory for score.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            return validate_command(args.fixture)
        if args.command == "evaluate":
            return evaluate_command(args.train, args.test, args.detector, args.output)
        if args.command == "demo":
            return demo_command(args.output)
        if args.command == "score":
            return score_command(args.fixture, args.alarms, args.output)
        parser.error(f"unknown command {args.command}")
        return 2
    except WaterLensError as exc:
        return _fail(exc)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        print(str(code), file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _emit({"status": "error", "category": "internal", "message": str(exc), "path": None, "row": None})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
