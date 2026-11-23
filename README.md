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

## Tests

```bash
PYTHONPATH=src python -m pytest
```

Fixture terms, seeds, and file checksums are in each `manifest.json`. The schedules are original and are documented in `docs/project-contract.md`.
