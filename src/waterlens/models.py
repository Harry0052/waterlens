"""Versioned shapes for readings, events, alarms, and reports."""

from dataclasses import dataclass, field
from datetime import datetime

READINGS_SCHEMA = "waterlens.readings.v1"
EVENTS_SCHEMA = "waterlens.events.v1"
ALARMS_SCHEMA = "waterlens.alarms.v1"
REPORT_SCHEMA = "waterlens.report.v1"
GENERATOR = "waterlens.schedule.v1"

READING_COLUMNS = [
    "household_id",
    "timestamp",
    "interval_seconds",
    "volume_liters",
    "provenance",
]
EVENT_COLUMNS = [
    "event_id",
    "household_id",
    "start",
    "end",
    "kind",
    "role",
    "volume_liters",
    "pulses",
]
ALARM_COLUMNS = [
    "alarm_id",
    "household_id",
    "detector_id",
    "start",
    "end",
    "provenance",
]

ALLOWED_INTERVALS = frozenset({300})
MAX_VOLUME_LITERS = 200.0
MIN_YEAR = 2000
MAX_YEAR = 2100
MAX_ROWS = 200_000
MAX_BYTES = 20 * 1024 * 1024
MAX_HOUSEHOLDS = 500
COVERAGE_MIN = 0.90
EVENT_OBSERVED_MIN = 0.50
FLOW_GRID = (0.25, 0.5, 1.0, 5.0)
PERSISTENCE_GRID_MINUTES = (5, 10, 15, 20)

KINDS = frozenset(
    {
        "shower",
        "appliance",
        "irrigation",
        "leak_persistent",
        "leak_intermittent",
    }
)
ROLES = frozenset({"normal_use", "planted_leak"})
READING_PROVENANCE = frozenset({"generated"})
ALARM_PROVENANCE = frozenset({"generated", "external"})
SPLITS = frozenset({"train", "test"})


@dataclass(frozen=True)
class Reading:
    household_id: str
    start: datetime
    end: datetime
    interval_seconds: int
    volume_liters: float
    provenance: str
    source_row: int
    timestamp_text: str


@dataclass(frozen=True)
class Event:
    event_id: str
    household_id: str
    start: datetime
    end: datetime
    kind: str
    role: str
    volume_liters: float
    pulses: tuple[datetime, ...]
    source_row: int
    start_text: str
    end_text: str
    pulse_text: str


@dataclass(frozen=True)
class Alarm:
    alarm_id: str
    household_id: str
    detector_id: str
    start: datetime
    end: datetime
    provenance: str
    evidence: tuple[str, ...] = ()
    start_text: str = ""
    end_text: str = ""


@dataclass(frozen=True)
class Conflict:
    household_id: str
    timestamp_text: str
    rows: tuple[int, ...]
    reason: str


@dataclass(frozen=True)
class Configuration:
    id: str
    seed: int
    split: str
    timezone: str
    interval_seconds: int
    households: tuple[str, ...]
    config_hash: str


@dataclass
class Fixture:
    manifest_path: str
    readings_path: str
    events_path: str
    readings: list[Reading]
    events: list[Event]
    configurations: list[Configuration]
    duplicates_ignored: int
    conflicts: list[Conflict]
    missing_intervals: list[dict] = field(default_factory=list)

    def timezone_for(self, household_id: str) -> str:
        for config in self.configurations:
            if household_id in config.households:
                return config.timezone
        raise KeyError(household_id)

    def split_households(self, split: str) -> list[str]:
        found: list[str] = []
        for config in self.configurations:
            if config.split == split:
                found.extend(config.households)
        return found
