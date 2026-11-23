# Grokbot progress

Index

| Phase | Status | Next |
| --- | --- | --- |
| P01 | PASS | P02 |
| P02 | PASS | P03 |
| P03 | not started | |
| P04 | not started | |
| P05 | not started | |
| P06 | not started | |
| P07 | not started | |

## P01 — Research overlap and confirm the MVP

- Phase and status: PASS
- Files changed: `docs/overlap.md`, `docs/project-contract.md`, `docs/grokbot-progress.md`
- Commands and results:
  - GitHub repository search on 2026-11-23 for the playbook queries returned `total_count: 0`.
  - `python3 -m pip install --target /tmp/p01-py pysimdeum==1.0.1` succeeded. Installed public API is `built_house`. A source scan found no leak, alarm, precision, recall, or ground-truth scoring.
  - Observed simulation of one household with pysimdeum 1.0.1 failed on Python 3.12.3 / pandas 3.1.1: `ValueError: Invalid frequency: 1H`.
  - `matlab` and `octave` are absent, so STREaM was not executed. README at commit `6cf74074655bb677bb89b9a1e813b47da051ad77` documents `outputTrajectory.mat` demand traces only.
  - Flume Usage Alerts page fetched (updated July 1, 2026). It documents resident notifications, including an irrigation exception. No local scorer exists.
  - engdino/water-leak-detection README describes unlabeled 15-minute apartment cumulative readings and has no license. Files were not downloaded.
- Artifact paths: `docs/overlap.md`, `docs/project-contract.md`
- Open issues: pySIMDEUM master was read and not executed. STREaM remains unexecuted until MATLAB is available. Neither gap blocks the MVP, because neither tool emits the acceptance score.
- Next phase: P02
- Decision recorded in the overlap note: proceed with an original generated fixture and two local baselines. Do not vendor the compared projects.

## P02 — Create the repository and data contracts

- Phase and status: PASS
- Files changed: `pyproject.toml`, `.gitignore`, `README.md`, `src/waterlens/__init__.py`, `src/waterlens/__main__.py`, `src/waterlens/errors.py`, `src/waterlens/models.py`, `src/waterlens/hashutil.py`, `src/waterlens/parse.py`, `src/waterlens/fixtures.py`, `src/waterlens/cli.py`, `tests/test_validate.py`, `fixtures/valid/`, `fixtures/invalid/`, `fixtures/heldout/`, `fixtures/oracle/valid_fixture.md`, `docs/grokbot-progress.md`
- Commands and results:
  - `PYTHONPATH=src python -m pytest tests/test_validate.py` → 7 passed.
  - `PYTHONPATH=src python -m waterlens validate fixtures/valid` → exit 0. Stderr: `validated fixtures/valid: 290 readings, 2 exact duplicates ignored, 0 conflicting timestamps quarantined, 1 missing intervals`. Stdout status `ok`. Train config hash `943a347b64b8e092285799ca0c2a3d5e6eeea362162bdb4b7917023715ac3996` (seed 11, split train). Fold config hash `9ca2dbd922482072378a99ff3df34b4dfc6d0e5940de931d2a7067c2e7fb9256` (seed 42, split train, America/New_York).
  - `PYTHONPATH=src python -m waterlens validate fixtures/invalid` → exit 2. Message: `volume_liters must be a number >= 0 and <= 200 liters per interval; got '-1.0000'` at `fixtures/invalid/readings.csv` row 3.
- Artifact paths: `fixtures/valid/`, `fixtures/invalid/`, `fixtures/heldout/`, `fixtures/oracle/valid_fixture.md`
- Open issues: scoring, detectors, and the HTML report are not in this phase. Held-out rows are generated so the frozen case is already on disk.
- Next phase: P03
