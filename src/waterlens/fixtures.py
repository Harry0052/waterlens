"""Original generated household schedules. Nothing here is a measured export."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from waterlens.hashutil import config_hash
from waterlens.models import GENERATOR

VOLUME_FORMAT = "{:.4f}"


@dataclass(frozen=True)
class EventSpec:
    event_id: str
    kind: str
    role: str
    start: time
    end: time
    volume_liters: float
    pulses: tuple[time, ...] = ()


@dataclass(frozen=True)
class Schedule:
    config_id: str
    seed: int
    split: str
    timezone: str
    household_id: str
    day: date
    events: tuple[EventSpec, ...]
    gap_at: time | None = None
    duplicate_midnight: bool = False
    move_last_to_front: bool = False


TRAIN = Schedule(
    config_id="train",
    seed=11,
    split="train",
    timezone="America/Los_Angeles",
    household_id="HH-TRAIN-01",
    day=date(2026, 6, 14),
    events=(
        EventSpec("E-TRAIN-SHOWER", "shower", "normal_use", time(7, 0), time(7, 10), 12.0),
        EventSpec("E-TRAIN-DISH", "appliance", "normal_use", time(12, 0), time(12, 10), 3.0),
        EventSpec("E-TRAIN-LEAK", "leak_persistent", "planted_leak", time(15, 0), time(15, 20), 0.4),
    ),
    gap_at=time(3, 0),
    duplicate_midnight=True,
    move_last_to_front=True,
)

HELDOUT = Schedule(
    config_id="test",
    seed=29,
    split="test",
    timezone="America/Los_Angeles",
    household_id="HH-HELD-01",
    day=date(2026, 6, 15),
    events=(
        EventSpec("E-HELD-SHOWER", "shower", "normal_use", time(7, 0), time(7, 10), 12.0),
        EventSpec("E-HELD-IRR", "irrigation", "normal_use", time(8, 0), time(8, 40), 1.2),
        EventSpec("E-HELD-LEAK-P", "leak_persistent", "planted_leak", time(10, 0), time(11, 0), 0.4),
        EventSpec(
            "E-HELD-LEAK-I",
            "leak_intermittent",
            "planted_leak",
            time(13, 0),
            time(13, 35),
            0.4,
            pulses=(time(13, 0), time(13, 15), time(13, 30)),
        ),
    ),
    gap_at=time(11, 30),
    duplicate_midnight=True,
    move_last_to_front=True,
)

# Repeated local hour on the 2026-11-01 America/New_York fold.
# 01:55 EDT is 05:55Z and is earlier than 01:00 EST (06:00Z).
FOLD_ROWS = (
    ("HH-FOLD-01", "2026-11-01T01:00:00-05:00", "300", "0.1000", "generated"),
    ("HH-FOLD-01", "2026-11-01T01:55:00-04:00", "300", "0.0000", "generated"),
    ("HH-FOLD-01", "2026-11-01T01:55:00-04:00", "300", "0.0000", "generated"),
    ("HH-FOLD-01", "2026-11-01T01:05:00-05:00", "300", "0.0000", "generated"),
)

FOLD_CONFIGURATION = {
    "id": "fold",
    "seed": 42,
    "split": "train",
    "timezone": "America/New_York",
    "interval_seconds": 300,
    "households": ["HH-FOLD-01"],
}


def configuration_payload(schedule: Schedule) -> dict:
    return {
        "generator": GENERATOR,
        "households": [schedule.household_id],
        "id": schedule.config_id,
        "interval_seconds": 300,
        "schema_version": "1",
        "seed": schedule.seed,
        "split": schedule.split,
        "timezone": schedule.timezone,
    }


def configuration_record(schedule: Schedule) -> dict:
    payload = configuration_payload(schedule)
    payload["config_hash"] = config_hash(payload)
    return payload


def fold_configuration_record() -> dict:
    payload = {
        "generator": GENERATOR,
        "households": list(FOLD_CONFIGURATION["households"]),
        "id": FOLD_CONFIGURATION["id"],
        "interval_seconds": FOLD_CONFIGURATION["interval_seconds"],
        "schema_version": "1",
        "seed": FOLD_CONFIGURATION["seed"],
        "split": FOLD_CONFIGURATION["split"],
        "timezone": FOLD_CONFIGURATION["timezone"],
    }
    payload["config_hash"] = config_hash(payload)
    return payload


def _local(day: date, clock: time, zone: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, clock.hour, clock.minute, clock.second, tzinfo=zone)


def local_slots(day: date, zone: ZoneInfo, interval_seconds: int = 300) -> list[datetime]:
    current = datetime(day.year, day.month, day.day, tzinfo=zone)
    slots: list[datetime] = []
    while True:
        slots.append(current)
        nxt = (current.astimezone(timezone.utc) + timedelta(seconds=interval_seconds)).astimezone(zone)
        if nxt.date() != day:
            break
        if len(slots) > 400:
            raise RuntimeError(f"slot generation did not reach the next local midnight for {day}")
        current = nxt
    return slots


def _format_local(moment: datetime, zone: ZoneInfo) -> str:
    return moment.astimezone(zone).isoformat(timespec="seconds")


def schedule_rows(schedule: Schedule) -> tuple[list[list[str]], list[list[str]]]:
    zone = ZoneInfo(schedule.timezone)
    slots = local_slots(schedule.day, zone)
    volumes = {slot: 0.0 for slot in slots}
    for event in schedule.events:
        start = _local(schedule.day, event.start, zone)
        end = _local(schedule.day, event.end, zone)
        pulse_starts = {_local(schedule.day, pulse, zone) for pulse in event.pulses}
        for slot in slots:
            if slot < start or slot >= end:
                continue
            if pulse_starts and slot not in pulse_starts:
                continue
            volumes[slot] += event.volume_liters
    gap = _local(schedule.day, schedule.gap_at, zone) if schedule.gap_at else None
    rows: list[list[str]] = []
    for slot in slots:
        if gap is not None and slot == gap:
            continue
        rows.append(
            [
                schedule.household_id,
                _format_local(slot, zone),
                "300",
                VOLUME_FORMAT.format(volumes[slot]),
                "generated",
            ]
        )
    if schedule.move_last_to_front and rows:
        last = rows.pop()
        rows.insert(0, last)
    if schedule.duplicate_midnight and rows:
        midnight = _format_local(slots[0], zone)
        original = next(row for row in rows if row[1] == midnight)
        rows.append(list(original))
    event_rows: list[list[str]] = []
    for event in schedule.events:
        start = _local(schedule.day, event.start, zone)
        end = _local(schedule.day, event.end, zone)
        pulses = ";".join(_format_local(_local(schedule.day, pulse, zone), zone) for pulse in event.pulses)
        event_rows.append(
            [
                event.event_id,
                schedule.household_id,
                _format_local(start, zone),
                _format_local(end, zone),
                event.kind,
                event.role,
                VOLUME_FORMAT.format(event.volume_liters),
                pulses,
            ]
        )
    return rows, event_rows


def render_csv(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def manifest_document(configurations: list[dict], files: dict[str, str]) -> str:
    document = {
        "schema_version": "1",
        "generator": GENERATOR,
        "generator_version": "0.1.0",
        "generated": True,
        "source_url": None,
        "license": "MIT",
        "use_terms": (
            "Original synthetic intervals generated in this repository. "
            "Not a measured household export and not derived from pySIMDEUM, STREaM, or Flume. "
            "Redistribution follows the repository MIT license."
        ),
        "attribution": "WaterLens contributors",
        "units": {"volume": "liters", "interval": "seconds"},
        "notes": "Synthetic generated intervals. Not a measured household export.",
        "files": {name: {"sha256": _sha256(text)} for name, text in files.items()},
        "configurations": configurations,
    }
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def write_schedule(directory: Path, schedule: Schedule) -> None:
    from waterlens.models import EVENT_COLUMNS, READING_COLUMNS

    readings, events = schedule_rows(schedule)
    readings_text = render_csv(READING_COLUMNS, readings)
    events_text = render_csv(EVENT_COLUMNS, events)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "readings.csv").write_text(readings_text, encoding="utf-8")
    (directory / "events.csv").write_text(events_text, encoding="utf-8")
    (directory / "manifest.json").write_text(
        manifest_document(
            [configuration_record(schedule)],
            {"readings.csv": readings_text, "events.csv": events_text},
        ),
        encoding="utf-8",
    )


def write_valid_bundle(directory: Path) -> None:
    from waterlens.models import EVENT_COLUMNS, READING_COLUMNS

    readings, events = schedule_rows(TRAIN)
    readings.extend(list(row) for row in FOLD_ROWS)
    readings_text = render_csv(READING_COLUMNS, readings)
    events_text = render_csv(EVENT_COLUMNS, events)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "readings.csv").write_text(readings_text, encoding="utf-8")
    (directory / "events.csv").write_text(events_text, encoding="utf-8")
    (directory / "manifest.json").write_text(
        manifest_document(
            [configuration_record(TRAIN), fold_configuration_record()],
            {"readings.csv": readings_text, "events.csv": events_text},
        ),
        encoding="utf-8",
    )


def write_invalid_bundle(directory: Path) -> None:
    from waterlens.models import EVENT_COLUMNS, READING_COLUMNS

    readings, events = schedule_rows(TRAIN)
    readings[1][3] = "-1.0000"
    readings_text = render_csv(READING_COLUMNS, readings)
    events_text = render_csv(EVENT_COLUMNS, events)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "readings.csv").write_text(readings_text, encoding="utf-8")
    (directory / "events.csv").write_text(events_text, encoding="utf-8")
    (directory / "manifest.json").write_text(
        manifest_document(
            [configuration_record(TRAIN)],
            {"readings.csv": readings_text, "events.csv": events_text},
        ),
        encoding="utf-8",
    )
