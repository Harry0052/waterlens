"""Causal baselines. An alarm can start only after enough past intervals qualify."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from waterlens.models import Alarm, Reading


@dataclass(frozen=True)
class DetectorParams:
    detector_id: str
    flow_threshold_liters: float
    persistence_minutes: int


def iter_runs(readings: list[Reading], household_id: str, flow_threshold_liters: float):
    """Yield above-threshold runs. A gap or a below-threshold reading starts a new run."""
    series = [item for item in readings if item.household_id == household_id]
    series.sort(key=lambda item: (item.start, item.source_row))
    run: list[Reading] = []
    for reading in series:
        above = reading.volume_liters >= flow_threshold_liters
        continuous = bool(run) and reading.start == run[-1].end
        if above and (not run or continuous):
            run.append(reading)
            continue
        if run:
            yield run
            run = []
        if above:
            run = [reading]
    if run:
        yield run


def predict(readings: list[Reading], params: DetectorParams, household_ids: list[str]) -> list[Alarm]:
    """Raise alarms without looking at later intervals to justify an earlier start.

    Persistence is measured from the start of the current above-threshold run.
    The alarm opens at the first interval whose own start is at least
    `persistence_minutes` after that run start. A zero persistence opens on the
    first qualifying interval. Missing intervals are already absent, so they
    break the run instead of being filled in.
    """
    alarms: list[Alarm] = []
    for household_id in sorted(household_ids):
        ordinal = 0
        for run in iter_runs(readings, household_id, params.flow_threshold_liters):
            anchor = run[0].start
            open_start = None
            open_end = None
            for reading in run:
                elapsed_minutes = (reading.start - anchor).total_seconds() / 60.0
                if elapsed_minutes + 1e-9 >= params.persistence_minutes:
                    if open_start is None:
                        open_start = reading.start
                    open_end = reading.end
            if open_start is None or open_end is None or open_end <= open_start:
                continue
            ordinal += 1
            alarms.append(
                Alarm(
                    alarm_id=f"{params.detector_id}-{household_id}-{ordinal:03d}",
                    household_id=household_id,
                    detector_id=params.detector_id,
                    start=open_start,
                    end=open_end,
                    provenance="generated",
                    evidence=tuple(item.timestamp_text for item in run),
                    start_text="",
                    end_text="",
                )
            )
    alarms.sort(key=lambda item: (item.household_id, item.start, item.alarm_id))
    return alarms


def readings_by_household(readings: list[Reading]) -> dict[str, list[Reading]]:
    grouped: dict[str, list[Reading]] = defaultdict(list)
    for reading in readings:
        grouped[reading.household_id].append(reading)
    return grouped
