# Valid fixture oracle

Hand count for `fixtures/valid`. The generator is `waterlens.schedule.v1`. These counts were calculated from the schedule, not copied from a previous program run.

## HH-TRAIN-01

- Timezone: America/Los_Angeles
- Day: 2026-06-14, which is not a daylight-saving transition
- Interval: 300 seconds
- Expected slots from local midnight to the next local midnight: 24 * 60 / 5 = 288
- Removed slot: 03:00 local. Remaining unique readings: 287
- The file repeats the midnight row once. That second copy is an exact duplicate and is not an extra observation.
- The 23:55 local row is written first. UTC order still starts at 00:00 local after parsing.
- Events: a 10-minute shower at 12.0 L/interval, a 10-minute appliance cycle at 3.0 L/interval, and a 20-minute persistent leak at 0.4 L/interval. None of those windows contain 03:00.

## HH-FOLD-01

- Timezone: America/New_York on 2026-11-01, the fall-back date
- `2026-11-01T01:55:00-04:00` is 05:55Z
- `2026-11-01T01:00:00-05:00` is 06:00Z
- `2026-11-01T01:05:00-05:00` is 06:05Z
- The 01:55 EDT row is repeated once. Unique fold readings: 3
- UTC order is 05:55Z, 06:00Z, 06:05Z even though the local clock labels are 01:55, 01:00, 01:05

## Totals the validator reports

- Readings kept: 287 + 3 = 290
- Exact duplicates ignored: 1 train + 1 fold = 2
- Conflicting timestamps: 0
- Missing intervals between kept readings: 1
- Configuration hashes are SHA-256 of the canonical JSON for each seed and split. They are stored in `manifest.json` and checked by recomputation.

## Invalid fixture

`fixtures/invalid` is the training schedule with one volume set to -1.0000. The validator must stop on that row and name `volume_liters`. It must not emit `"status": "ok"`.
