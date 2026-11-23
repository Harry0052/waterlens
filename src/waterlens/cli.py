"""Command line entry point. Machine output goes to stdout; notes go to stderr."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

from waterlens.errors import WaterLensError
from waterlens.parse import load_fixture


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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command == "validate":
            return validate_command(args.fixture)
        parser.error(f"unknown command {args.command}")
        return 2
    except WaterLensError as exc:
        return _fail(exc)
    except BrokenPipeError:
        return 0
    except Exception as exc:
        print(f"internal error: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        _emit({"status": "error", "category": "internal", "message": str(exc), "path": None, "row": None})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
