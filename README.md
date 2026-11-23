# WaterLens

Benchmark water-leak detectors against generated household usage patterns, and show where normal use triggers false alerts.

WaterLens is a local scoring harness. It does not connect to a meter, shut off water, or decide that a building has a leak. Every fixture shipped here is synthetic.

## Setup

Python 3.11 or newer. No runtime packages.

```bash
python -m pip install -e ".[dev]"
```

The demo and the validator also run without an editable install:

```bash
PYTHONPATH=src python -m waterlens --help
```

## Validate a fixture

Accept the labeled bundle (exact duplicate row, one missing interval, a repeated local hour on a timezone fold, and a configuration hash for each seed and split):

```bash
PYTHONPATH=src python -m waterlens validate fixtures/valid
```

Exit 0. Stdout is a JSON object with `"status": "ok"`. The command reports ignored duplicate rows and missing intervals on stderr.

Reject the negative-volume bundle:

```bash
PYTHONPATH=src python -m waterlens validate fixtures/invalid
```

Exit 2. Stdout is JSON with `"category": "value"` and a message that names `volume_liters`, the offending value, the file, and the row.

## Demo

Generate the training household and the held-out household, tune both baselines on the training split, and write the comparison:

```bash
PYTHONPATH=src python -m waterlens demo --output out/demo
```

Exit 0. The report is `out/demo/report.html`. The same figures are in `out/demo/summary.txt`, and `out/demo/score.json` is the machine-readable copy. On the held-out day the persistence baseline has precision 0.5, recall 0.5, a 15-minute median delay, and 1 false alert per eligible household-day. That false alert is the irrigation run. The intermittent planted leak is missed.

Open `report.html` in a browser. The skip link moves to the time-series table. A row for `E-HELD-LEAK-P` names `fixtures/heldout/readings.csv` under the output directory; that file has the 10:00 interval at 0.4000 liters.

Score an alarm file you already computed. WaterLens validates the CSV and does not execute it:

```bash
PYTHONPATH=src python -m waterlens score --fixture fixtures/heldout --alarms out/demo/alarms_persistence.csv --output out/external
```

A bad fixture stops with exit 2 and a JSON error on stdout. For example, `fixtures/invalid` has a negative volume and the message names `volume_liters` and the row.

## Tests

```bash
PYTHONPATH=src python -m pytest
```

Fixture terms, seeds, and file checksums are in each `manifest.json`. The schedules are original and are documented in `docs/project-contract.md`.
