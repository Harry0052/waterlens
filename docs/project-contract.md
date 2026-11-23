# Project contract

Status: accepted for implementation after the P01 overlap review (`docs/overlap.md`).

## User and task

A household water-conservation researcher, or a utility analytics developer, evaluates leak signatures before anyone proposes an alert to residents.

The task WaterLens supports:

1. Load one synthetic household interval-meter bundle (one meter, scheduled 5-minute volumes, labeled normal use and planted leaks).
2. Validate the bundle, or read a clear error if it is malformed.
3. Tune two baseline detectors on training households only.
4. Score those detectors, or an external alarm CSV, on held-out households.
5. Read event precision, recall, median detection delay, and false alerts per eligible household-day, with the event and alarm timestamps on one timeline.

## MVP boundary

In scope:

- One meter per household.
- Scheduled interval consumption in liters.
- Two planted leak kinds: persistent flow and intermittent pulses.
- Two baselines: an instantaneous volume threshold, and a causal persistence rule.
- Event-level one-to-one matching, delay, and false alerts per eligible household-day.
- An external alarm CSV that is validated and scored, never executed.
- A static HTML report with an accessible time-series table.

Out of scope:

- Live meters, automatic shutoff, billing, water quality, and inspection conclusions.
- Network or district-meter leaks.
- Loading or running third-party model code.
- Real household exports. Every bundled measurement is generated.

Measurements are labeled generated. A household-day with too few observed intervals is excluded from the false-alert denominator and named in the report.

## Minimum dependencies

- Python 3.11 or newer. The standard library supplies `zoneinfo`, CSV, JSON, and hashing.
- pytest 9.2.0 for the test extra only.
- No runtime package, no network fetch, and no paid service.
- Not required: pySIMDEUM (EUPL-1.2, and 1.0.1 did not simulate here), STREaM (GPL-3.0, MATLAB), Flume.

Provenance path for fixtures: original schedules written in this repository, seeds and split ids hashed into a configuration id. No external series is copied.

## Acceptance case

Frozen held-out household, persistence baseline tuned only on a disjoint training household:

- The detector matches one planted persistent leak.
- Detection delay for that match is 15 minutes.
- The same detector raises one alarm on a sustained normal irrigation run and does not match it to a planted leak.
- A second planted leak (intermittent pulses) is unmatched.
- Event precision is 0.5.
- Event recall is 0.5.
- The report shows the event timestamps and the alarm timestamps for the match, the false alarm, and the miss.

Independent checks that travel with this case:

- Two alarms that overlap one planted event produce one true positive, not two.
- Exact duplicate rows collapse. Conflicting duplicate timestamps are quarantined and are not evidence.
- Unsorted rows and repeated local clock times during a timezone fold are ordered by UTC.
- A missing interval breaks a persistence run and is listed. It is not interpolated.
- Editing or adding a held-out household does not change the tuned parameters.

Numeric tolerance for this case is exact equality. The rules are counts and minute differences, not a fitted approximation.

## Recommendation

Build WaterLens in this repository. Do not open the MVP by integrating pySIMDEUM or STREaM. Either project can still be a future, optional, out-of-repo trace source if someone exports interval liters and event labels into the CSV contract. That export is not part of this release.
