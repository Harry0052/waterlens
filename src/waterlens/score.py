"""One-to-one event matching and the acceptance metrics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from waterlens.detectors import DetectorParams, predict
from waterlens.fixtures import local_slots
from waterlens.models import (
    COVERAGE_MIN,
    EVENT_OBSERVED_MIN,
    FLOW_GRID,
    PERSISTENCE_GRID_MINUTES,
    REPORT_SCHEMA,
    Alarm,
    Event,
    Reading,
)
from waterlens import __version__

LIMITATIONS = [
    "Every bundled volume is generated. A score is not a statement about a real building.",
    "One meter per household. No shutoff, billing, water-quality, or inspection conclusion.",
    "The threshold and persistence baselines are reference rules, not a commercial detector.",
    "Missing intervals are listed and are not interpolated into a qualified run.",
    "An alarm uses only the current run. Later readings do not move its start earlier.",
    "A household-day below 90 percent observed slots is omitted from the false-alert denominator.",
]


def _interval_for(readings: list[Reading], household_id: str) -> int:
    for reading in readings:
        if reading.household_id == household_id:
            return reading.interval_seconds
    raise KeyError(household_id)


def event_slot_starts(event: Event, interval_seconds: int) -> list[datetime]:
    slots: list[datetime] = []
    cursor = event.start
    while cursor < event.end:
        slots.append(cursor)
        cursor += timedelta(seconds=interval_seconds)
    return slots


def coverage_ratio(event: Event, observed: set[datetime], interval_seconds: int) -> float:
    slots = event_slot_starts(event, interval_seconds)
    if not slots:
        return 0.0
    seen = sum(1 for slot in slots if slot in observed)
    return seen / len(slots)


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def match_events(events: list[Event], alarms: list[Alarm], evaluable_ids: set[str]) -> list[tuple[Event, Alarm]]:
    """Greedy one-to-one overlap.

    Candidates are sorted by event start, event id, alarm start, then alarm id.
    The first free pair wins. A second alarm that overlaps the same planted
    event stays unmatched.
    """
    planted = [event for event in events if event.role == "planted_leak" and event.event_id in evaluable_ids]
    pairs: list[tuple[Event, Alarm]] = []
    for event in planted:
        for alarm in alarms:
            if alarm.household_id != event.household_id:
                continue
            if _overlaps(alarm.start, alarm.end, event.start, event.end):
                pairs.append((event, alarm))
    pairs.sort(key=lambda item: (item[0].start, item[0].event_id, item[1].start, item[1].alarm_id))
    used_events: set[str] = set()
    used_alarms: set[str] = set()
    matches: list[tuple[Event, Alarm]] = []
    for event, alarm in pairs:
        if event.event_id in used_events or alarm.alarm_id in used_alarms:
            continue
        used_events.add(event.event_id)
        used_alarms.add(alarm.alarm_id)
        matches.append((event, alarm))
    return matches


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def household_day_status(
    readings: list[Reading],
    household_ids: list[str],
    timezones: dict[str, str],
) -> tuple[int, list[dict]]:
    eligible = 0
    excluded: list[dict] = []
    for household_id in sorted(household_ids):
        zone = ZoneInfo(timezones[household_id])
        observed: dict = defaultdict(set)
        interval = _interval_for(readings, household_id)
        for reading in readings:
            if reading.household_id != household_id:
                continue
            observed[reading.start.astimezone(zone).date()].add(reading.start.astimezone(timezone.utc))
        for day in sorted(observed):
            expected = {
                slot.astimezone(timezone.utc) for slot in local_slots(day, zone, interval)
            }
            coverage = len(observed[day]) / len(expected) if expected else 0.0
            record = {
                "household_id": household_id,
                "date": day.isoformat(),
                "coverage": round(coverage, 6),
                "expected_intervals": len(expected),
                "observed_intervals": len(observed[day]),
            }
            if coverage + 1e-12 >= COVERAGE_MIN:
                eligible += 1
            else:
                record["reason"] = "insufficient_coverage"
                excluded.append(record)
    return eligible, excluded


def _stamp(moment: datetime, zone_name: str) -> str:
    return moment.astimezone(ZoneInfo(zone_name)).isoformat(timespec="seconds")


def score_alarms(
    readings: list[Reading],
    events: list[Event],
    alarms: list[Alarm],
    household_ids: list[str],
    timezones: dict[str, str],
    *,
    parameters: DetectorParams | None = None,
    source_readings: str = "",
    missing: list[dict] | None = None,
    config_hashes: dict | None = None,
    train_households: list[str] | None = None,
) -> dict:
    selected = set(household_ids)
    scoped_events = [event for event in events if event.household_id in selected]
    scoped_alarms = [alarm for alarm in alarms if alarm.household_id in selected]
    observed: dict[str, set[datetime]] = defaultdict(set)
    for reading in readings:
        if reading.household_id in selected:
            observed[reading.household_id].add(reading.start)
    evaluable: set[str] = set()
    unevaluable: list[dict] = []
    for event in scoped_events:
        if event.role != "planted_leak":
            continue
        ratio = coverage_ratio(event, observed[event.household_id], _interval_for(readings, event.household_id))
        if ratio + 1e-12 >= EVENT_OBSERVED_MIN:
            evaluable.add(event.event_id)
        else:
            unevaluable.append(
                {
                    "event_id": event.event_id,
                    "household_id": event.household_id,
                    "observed_fraction": round(ratio, 6),
                    "reason": "too_few_observed_intervals",
                }
            )
    matches = match_events(scoped_events, scoped_alarms, evaluable)
    matched_event_ids = {event.event_id for event, _alarm in matches}
    matched_alarm_ids = {alarm.alarm_id for _event, alarm in matches}
    delays = [(alarm.start - event.start).total_seconds() / 60.0 for event, alarm in matches]
    planted = [event for event in scoped_events if event.role == "planted_leak" and event.event_id in evaluable]
    true_positives = len(matches)
    false_positives = len(scoped_alarms) - true_positives
    false_negatives = len(planted) - true_positives
    precision = true_positives / len(scoped_alarms) if scoped_alarms else None
    recall = true_positives / len(planted) if planted else None
    eligible, excluded = household_day_status(readings, household_ids, timezones)
    false_alerts = false_positives
    rate = false_alerts / eligible if eligible else None
    zone_for = timezones

    def event_view(event: Event, alarm: Alarm | None, delay: float | None) -> dict:
        zone_name = zone_for[event.household_id]
        view = {
            "event_id": event.event_id,
            "household_id": event.household_id,
            "kind": event.kind,
            "role": event.role,
            "event_start": _stamp(event.start, zone_name),
            "event_end": _stamp(event.end, zone_name),
            "source_readings": source_readings,
        }
        if alarm is not None:
            view.update(
                {
                    "alarm_id": alarm.alarm_id,
                    "alarm_start": _stamp(alarm.start, zone_name),
                    "alarm_end": _stamp(alarm.end, zone_name),
                    "delay_minutes": delay,
                    "evidence": list(alarm.evidence),
                }
            )
        return view

    match_views = [
        event_view(event, alarm, (alarm.start - event.start).total_seconds() / 60.0)
        for event, alarm in matches
    ]
    unmatched_alarms = []
    for alarm in scoped_alarms:
        if alarm.alarm_id in matched_alarm_ids:
            continue
        zone_name = zone_for[alarm.household_id]
        unmatched_alarms.append(
            {
                "alarm_id": alarm.alarm_id,
                "household_id": alarm.household_id,
                "detector_id": alarm.detector_id,
                "alarm_start": _stamp(alarm.start, zone_name),
                "alarm_end": _stamp(alarm.end, zone_name),
                "evidence": list(alarm.evidence),
                "source_readings": source_readings,
            }
        )
    unmatched_events = [
        event_view(event, None, None)
        for event in planted
        if event.event_id not in matched_event_ids
    ]
    return {
        "schema_version": REPORT_SCHEMA,
        "software_version": __version__,
        "generated": True,
        "units": {
            "volume": "liters_per_interval",
            "delay": "minutes",
            "false_alerts": "count_per_eligible_household_day",
        },
        "detector_id": parameters.detector_id if parameters else (scoped_alarms[0].detector_id if scoped_alarms else "external"),
        "parameters": None
        if parameters is None
        else {
            "flow_threshold_liters": parameters.flow_threshold_liters,
            "persistence_minutes": parameters.persistence_minutes,
        },
        "train_households": list(train_households or []),
        "test_households": list(household_ids),
        "config_hashes": config_hashes or {},
        "precision": precision,
        "recall": recall,
        "median_delay_minutes": _median(delays),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "unevaluable_events": unevaluable,
        "false_alerts": false_alerts,
        "eligible_household_days": eligible,
        "excluded_household_days": excluded,
        "false_alerts_per_eligible_household_day": rate,
        "matches": match_views,
        "unmatched_alarms": unmatched_alarms,
        "unmatched_events": unmatched_events,
        "missing_intervals": missing or [],
        "limitations": list(LIMITATIONS),
    }


def tune(readings: list[Reading], events: list[Event], household_ids: list[str], detector_id: str, timezones: dict[str, str]) -> DetectorParams:
    """Pick parameters from the training households only.

    Rank by higher planted-leak recall, then fewer false alarms, then a higher
    flow threshold, then a longer persistence. Held-out rows are not an argument
    to this function.
    """
    if detector_id == "persistence":
        grid = [(flow, minutes) for flow in FLOW_GRID for minutes in PERSISTENCE_GRID_MINUTES]
    elif detector_id == "threshold":
        grid = [(flow, 0) for flow in FLOW_GRID]
    else:
        raise ValueError(f"unknown detector {detector_id}")
    best_key = None
    best_params = None
    for flow, minutes in grid:
        params = DetectorParams(detector_id, flow, minutes)
        alarms = predict(readings, params, household_ids)
        report = score_alarms(readings, events, alarms, household_ids, timezones, parameters=params)
        recall = -1.0 if report["recall"] is None else report["recall"]
        key = (recall, -report["false_positives"], flow, minutes)
        if best_key is None or key > best_key:
            best_key = key
            best_params = params
    assert best_params is not None
    return best_params
