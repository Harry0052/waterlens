"""Parse fixture CSV into UTC liters and quarantine bad evidence."""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from waterlens.errors import WaterLensError
from waterlens.hashutil import config_hash
from waterlens.models import (
    ALARM_COLUMNS,
    ALARM_PROVENANCE,
    ALLOWED_INTERVALS,
    EVENT_COLUMNS,
    KINDS,
    MAX_BYTES,
    MAX_HOUSEHOLDS,
    MAX_ROWS,
    MAX_VOLUME_LITERS,
    MAX_YEAR,
    MIN_YEAR,
    READING_COLUMNS,
    READING_PROVENANCE,
    ROLES,
    SPLITS,
    Alarm,
    Configuration,
    Conflict,
    Event,
    Fixture,
    Reading,
)

_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def parse_timestamp(text: str, *, path: str, row: int, field_name: str = "timestamp") -> datetime:
    raw = text.strip()
    if not raw:
        raise WaterLensError("schema", f"{field_name} is empty", path=path, row=row)
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise WaterLensError(
            "value",
            f"{field_name} must be ISO-8601 with a numeric UTC offset; got {text!r}",
            path=path,
            row=row,
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WaterLensError(
            "value",
            f"{field_name} needs a numeric UTC offset; got {text!r}",
            path=path,
            row=row,
        )
    utc = parsed.astimezone(timezone.utc)
    if not MIN_YEAR <= utc.year <= MAX_YEAR:
        raise WaterLensError(
            "value",
            f"{field_name} year must be inside {MIN_YEAR}-{MAX_YEAR}; got {text!r}",
            path=path,
            row=row,
        )
    return utc


def parse_volume(text: str, *, path: str, row: int) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise WaterLensError(
            "value",
            f"volume_liters must be a number >= 0 and <= {MAX_VOLUME_LITERS:g} liters per interval; got {text!r}",
            path=path,
            row=row,
        ) from exc
    if not math.isfinite(value) or value < 0 or value > MAX_VOLUME_LITERS:
        raise WaterLensError(
            "value",
            f"volume_liters must be a number >= 0 and <= {MAX_VOLUME_LITERS:g} liters per interval; got {text!r}",
            path=path,
            row=row,
        )
    return value


def _check_id(value: str, *, field_name: str, path: str, row: int) -> str:
    if not _ID.fullmatch(value):
        raise WaterLensError(
            "value",
            f"{field_name} must match [A-Za-z0-9_-] and be 1-64 characters; got {value!r}",
            path=path,
            row=row,
        )
    return value


def read_csv_table(
    path: Path,
    columns: list[str],
    *,
    max_bytes: int = MAX_BYTES,
    max_rows: int = MAX_ROWS,
) -> list[tuple[int, dict[str, str]]]:
    if not path.is_file():
        raise WaterLensError("io", f"file not found: {path}", path=str(path))
    size = path.stat().st_size
    if size > max_bytes:
        raise WaterLensError(
            "bound",
            f"{path} is {size} bytes; the limit is {max_bytes} bytes",
            path=str(path),
        )
    text = path.read_text(encoding="utf-8")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise WaterLensError("schema", "CSV has no header row", path=str(path))
    fields = [name.strip() for name in reader.fieldnames]
    if fields != columns:
        raise WaterLensError(
            "schema",
            f"columns must be {', '.join(columns)}; got {', '.join(fields)}",
            path=str(path),
        )
    rows: list[tuple[int, dict[str, str]]] = []
    for index, raw in enumerate(reader, start=2):
        if len(rows) >= max_rows:
            raise WaterLensError(
                "bound",
                f"row limit is {max_rows}",
                path=str(path),
                row=index,
            )
        rows.append((index, {column: (raw.get(column) or "").strip() for column in columns}))
    if not rows:
        raise WaterLensError("schema", "CSV has a header but no data rows", path=str(path))
    return rows


def load_manifest(path: Path) -> list[Configuration]:
    if not path.is_file():
        raise WaterLensError("io", f"file not found: {path}", path=str(path))
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise WaterLensError("bound", f"{path} is {size} bytes; the limit is {MAX_BYTES} bytes", path=str(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WaterLensError("schema", f"manifest is not JSON: {exc}", path=str(path)) from exc
    if not isinstance(document, dict) or document.get("schema_version") != "1":
        raise WaterLensError("schema", "manifest schema_version must be 1", path=str(path))
    if document.get("generator") != "waterlens.schedule.v1":
        raise WaterLensError(
            "schema",
            "manifest generator must be waterlens.schedule.v1",
            path=str(path),
        )
    configs = document.get("configurations")
    if not isinstance(configs, list) or not configs:
        raise WaterLensError("schema", "manifest configurations must be a non-empty list", path=str(path))
    parsed: list[Configuration] = []
    seen: set[str] = set()
    for item in configs:
        if not isinstance(item, dict):
            raise WaterLensError("schema", "each configuration must be an object", path=str(path))
        households = item.get("households")
        if not isinstance(households, list) or not households:
            raise WaterLensError("schema", "configuration households must be a non-empty list", path=str(path))
        household_ids = tuple(str(value) for value in households)
        for household_id in household_ids:
            if not _ID.fullmatch(household_id):
                raise WaterLensError(
                    "value",
                    f"household id {household_id!r} must match [A-Za-z0-9_-]",
                    path=str(path),
                )
            if household_id in seen:
                raise WaterLensError(
                    "value",
                    f"household {household_id} appears in more than one configuration",
                    path=str(path),
                )
            seen.add(household_id)
        split = str(item.get("split", ""))
        if split not in SPLITS:
            raise WaterLensError("value", f"split must be train or test; got {split!r}", path=str(path))
        timezone_name = str(item.get("timezone", ""))
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise WaterLensError(
                "value",
                f"timezone is not a known zoneinfo name: {timezone_name!r}",
                path=str(path),
            ) from exc
        try:
            interval = int(item["interval_seconds"])
            seed = int(item["seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WaterLensError(
                "schema",
                "configuration needs integer seed and interval_seconds",
                path=str(path),
            ) from exc
        if interval not in ALLOWED_INTERVALS:
            raise WaterLensError(
                "value",
                f"interval_seconds must be one of {sorted(ALLOWED_INTERVALS)}; got {interval}",
                path=str(path),
            )
        payload = {
            "generator": document["generator"],
            "households": list(household_ids),
            "id": str(item.get("id", "")),
            "interval_seconds": interval,
            "schema_version": document["schema_version"],
            "seed": seed,
            "split": split,
            "timezone": timezone_name,
        }
        expected = config_hash(payload)
        if item.get("config_hash") != expected:
            raise WaterLensError(
                "value",
                f"config_hash for {payload['id']!r} does not match the seed and split ({expected})",
                path=str(path),
            )
        parsed.append(
            Configuration(
                id=payload["id"],
                seed=seed,
                split=split,
                timezone=timezone_name,
                interval_seconds=interval,
                households=household_ids,
                config_hash=expected,
            )
        )
    if len(seen) > MAX_HOUSEHOLDS:
        raise WaterLensError("bound", f"household limit is {MAX_HOUSEHOLDS}", path=str(path))
    return parsed


def parse_readings(
    path: Path,
    *,
    max_bytes: int = MAX_BYTES,
    max_rows: int = MAX_ROWS,
) -> tuple[list[Reading], int, list[Conflict]]:
    grouped: dict[tuple[str, datetime], list[Reading]] = defaultdict(list)
    duplicates = 0
    for row_number, row in read_csv_table(path, READING_COLUMNS, max_bytes=max_bytes, max_rows=max_rows):
        household_id = _check_id(row["household_id"], field_name="household_id", path=str(path), row=row_number)
        start = parse_timestamp(row["timestamp"], path=str(path), row=row_number)
        try:
            interval = int(row["interval_seconds"])
        except ValueError as exc:
            raise WaterLensError(
                "value",
                f"interval_seconds must be an integer in {sorted(ALLOWED_INTERVALS)}; got {row['interval_seconds']!r}",
                path=str(path),
                row=row_number,
            ) from exc
        if interval not in ALLOWED_INTERVALS:
            raise WaterLensError(
                "value",
                f"interval_seconds must be one of {sorted(ALLOWED_INTERVALS)}; got {interval}",
                path=str(path),
                row=row_number,
            )
        volume = parse_volume(row["volume_liters"], path=str(path), row=row_number)
        if row["provenance"] not in READING_PROVENANCE:
            raise WaterLensError(
                "value",
                "provenance must be 'generated'; bundled and uploaded readings are labeled measurements only when generated",
                path=str(path),
                row=row_number,
            )
        grouped[(household_id, start)].append(
            Reading(
                household_id=household_id,
                start=start,
                end=start + timedelta(seconds=interval),
                interval_seconds=interval,
                volume_liters=volume,
                provenance=row["provenance"],
                source_row=row_number,
                timestamp_text=row["timestamp"],
            )
        )
    kept: list[Reading] = []
    conflicts: list[Conflict] = []
    for key in sorted(grouped, key=lambda item: (item[0], item[1])):
        bucket = grouped[key]
        first = bucket[0]
        if all(
            item.volume_liters == first.volume_liters
            and item.interval_seconds == first.interval_seconds
            and item.provenance == first.provenance
            for item in bucket
        ):
            duplicates += len(bucket) - 1
            kept.append(first)
            continue
        conflicts.append(
            Conflict(
                household_id=first.household_id,
                timestamp_text=first.timestamp_text,
                rows=tuple(item.source_row for item in bucket),
                reason="conflicting volume or interval at the same household timestamp; quarantined",
            )
        )
    households = {item.household_id for item in kept}
    if len(households) > MAX_HOUSEHOLDS:
        raise WaterLensError("bound", f"household limit is {MAX_HOUSEHOLDS}", path=str(path))
    kept.sort(key=lambda item: (item.household_id, item.start, item.source_row))
    _reject_overlapping_buckets(kept, path)
    return kept, duplicates, conflicts


def _reject_overlapping_buckets(readings: list[Reading], path: Path) -> None:
    by_household: dict[str, list[Reading]] = defaultdict(list)
    for reading in readings:
        by_household[reading.household_id].append(reading)
    for household_id, series in by_household.items():
        series.sort(key=lambda item: item.start)
        for previous, current in zip(series, series[1:]):
            if current.start < previous.end:
                raise WaterLensError(
                    "value",
                    f"household {household_id} has overlapping intervals at {previous.timestamp_text} and {current.timestamp_text}",
                    path=str(path),
                    row=current.source_row,
                )


def missing_intervals(readings: list[Reading]) -> list[dict]:
    by_household: dict[str, list[Reading]] = defaultdict(list)
    for reading in readings:
        by_household[reading.household_id].append(reading)
    missing: list[dict] = []
    for household_id, series in by_household.items():
        series.sort(key=lambda item: item.start)
        for previous, current in zip(series, series[1:]):
            cursor = previous.end
            while cursor < current.start:
                missing.append(
                    {
                        "household_id": household_id,
                        "start": cursor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        "reason": "missing_interval",
                    }
                )
                cursor += timedelta(seconds=previous.interval_seconds)
                if len(missing) > MAX_ROWS:
                    raise WaterLensError("bound", "too many missing intervals to report", path=household_id)
    return missing


def parse_events(path: Path, readings: list[Reading], *, max_bytes: int = MAX_BYTES, max_rows: int = MAX_ROWS) -> list[Event]:
    known = {item.household_id for item in readings}
    intervals = {item.household_id: item.interval_seconds for item in readings}
    events: list[Event] = []
    seen: set[str] = set()
    for row_number, row in read_csv_table(path, EVENT_COLUMNS, max_bytes=max_bytes, max_rows=max_rows):
        event_id = _check_id(row["event_id"], field_name="event_id", path=str(path), row=row_number)
        if event_id in seen:
            raise WaterLensError("value", f"duplicate event_id {event_id}", path=str(path), row=row_number)
        seen.add(event_id)
        household_id = _check_id(row["household_id"], field_name="household_id", path=str(path), row=row_number)
        if household_id not in known:
            raise WaterLensError(
                "value",
                f"event {event_id} household {household_id} has no readings",
                path=str(path),
                row=row_number,
            )
        start = parse_timestamp(row["start"], path=str(path), row=row_number, field_name="start")
        end = parse_timestamp(row["end"], path=str(path), row=row_number, field_name="end")
        if end <= start:
            raise WaterLensError("value", f"event {event_id} end must be after start", path=str(path), row=row_number)
        if row["kind"] not in KINDS:
            raise WaterLensError(
                "value",
                f"kind must be one of {sorted(KINDS)}; got {row['kind']!r}",
                path=str(path),
                row=row_number,
            )
        if row["role"] not in ROLES:
            raise WaterLensError(
                "value",
                f"role must be one of {sorted(ROLES)}; got {row['role']!r}",
                path=str(path),
                row=row_number,
            )
        volume = parse_volume(row["volume_liters"], path=str(path), row=row_number)
        pulses: list[datetime] = []
        if row["pulses"]:
            for piece in row["pulses"].split(";"):
                pulses.append(parse_timestamp(piece, path=str(path), row=row_number, field_name="pulses"))
            for pulse in pulses:
                if pulse < start or pulse >= end:
                    raise WaterLensError(
                        "value",
                        f"event {event_id} pulse {piece!r} is outside the event interval",
                        path=str(path),
                        row=row_number,
                    )
        interval = intervals[household_id]
        if int((end - start).total_seconds()) % interval != 0:
            raise WaterLensError(
                "value",
                f"event {event_id} duration is not a multiple of {interval} seconds",
                path=str(path),
                row=row_number,
            )
        events.append(
            Event(
                event_id=event_id,
                household_id=household_id,
                start=start,
                end=end,
                kind=row["kind"],
                role=row["role"],
                volume_liters=volume,
                pulses=tuple(pulses),
                source_row=row_number,
                start_text=row["start"],
                end_text=row["end"],
                pulse_text=row["pulses"],
            )
        )
    events.sort(key=lambda item: (item.household_id, item.start, item.event_id))
    return events


def parse_alarms(path: Path, readings: list[Reading], *, max_bytes: int = MAX_BYTES, max_rows: int = MAX_ROWS) -> list[Alarm]:
    known = {item.household_id for item in readings}
    alarms: list[Alarm] = []
    seen: set[str] = set()
    for row_number, row in read_csv_table(path, ALARM_COLUMNS, max_bytes=max_bytes, max_rows=max_rows):
        alarm_id = _check_id(row["alarm_id"], field_name="alarm_id", path=str(path), row=row_number)
        if alarm_id in seen:
            raise WaterLensError("value", f"duplicate alarm_id {alarm_id}", path=str(path), row=row_number)
        seen.add(alarm_id)
        household_id = _check_id(row["household_id"], field_name="household_id", path=str(path), row=row_number)
        if household_id not in known:
            raise WaterLensError(
                "value",
                f"alarm {alarm_id} household {household_id} has no readings",
                path=str(path),
                row=row_number,
            )
        detector_id = _check_id(row["detector_id"], field_name="detector_id", path=str(path), row=row_number)
        start = parse_timestamp(row["start"], path=str(path), row=row_number, field_name="start")
        end = parse_timestamp(row["end"], path=str(path), row=row_number, field_name="end")
        if end <= start:
            raise WaterLensError("value", f"alarm {alarm_id} end must be after start", path=str(path), row=row_number)
        if row["provenance"] not in ALARM_PROVENANCE:
            raise WaterLensError(
                "value",
                "alarm provenance must be 'generated' or 'external'",
                path=str(path),
                row=row_number,
            )
        alarms.append(
            Alarm(
                alarm_id=alarm_id,
                household_id=household_id,
                detector_id=detector_id,
                start=start,
                end=end,
                provenance=row["provenance"],
                start_text=row["start"],
                end_text=row["end"],
            )
        )
    alarms.sort(key=lambda item: (item.household_id, item.start, item.alarm_id))
    return alarms


def load_fixture(directory: Path, *, max_bytes: int = MAX_BYTES, max_rows: int = MAX_ROWS) -> Fixture:
    if not directory.is_dir():
        raise WaterLensError("io", f"fixture directory not found: {directory}", path=str(directory))
    readings_path = directory / "readings.csv"
    events_path = directory / "events.csv"
    manifest_path = directory / "manifest.json"
    configurations = load_manifest(manifest_path)
    readings, duplicates, conflicts = parse_readings(readings_path, max_bytes=max_bytes, max_rows=max_rows)
    declared = {household for config in configurations for household in config.households}
    present = {item.household_id for item in readings}
    missing_households = sorted(declared - present)
    if missing_households:
        raise WaterLensError(
            "value",
            f"manifest households have no readings: {', '.join(missing_households)}",
            path=str(readings_path),
        )
    extra = sorted(present - declared)
    if extra:
        raise WaterLensError(
            "value",
            f"readings mention households that are not in the manifest: {', '.join(extra)}",
            path=str(readings_path),
        )
    events = parse_events(events_path, readings, max_bytes=max_bytes, max_rows=max_rows)
    return Fixture(
        manifest_path=str(manifest_path),
        readings_path=str(readings_path),
        events_path=str(events_path),
        readings=readings,
        events=events,
        configurations=configurations,
        duplicates_ignored=duplicates,
        conflicts=conflicts,
        missing_intervals=missing_intervals(readings),
    )
