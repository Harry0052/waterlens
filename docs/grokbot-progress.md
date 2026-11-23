# Grokbot progress

Index

| Phase | Status | Next |
| --- | --- | --- |
| P01 | PASS | P02 |
| P02 | PASS | P03 |
| P03 | PASS | P04 |
| P04 | PASS | P05 |
| P05 | PASS | P06 |
| P06 | PASS | P07 |
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

## P03 — Build the working core

- Phase and status: PASS
- Files changed: `src/waterlens/detectors.py`, `src/waterlens/score.py`, `src/waterlens/cli.py`, `tests/test_score.py`, `fixtures/oracle/heldout_persistence.json`, `fixtures/oracle/heldout_persistence.md`, `docs/evidence/p03/score.json`, `docs/evidence/p03/summary.txt`, `docs/grokbot-progress.md`
- Commands and results:
  - `PYTHONPATH=src python -m pytest tests/test_score.py tests/test_validate.py` → 12 passed.
  - `PYTHONPATH=src python -m waterlens evaluate --train fixtures/valid --test fixtures/heldout --detector persistence --output docs/evidence/p03` → exit 0.
  - Observed score: precision 0.5, recall 0.5, median delay 15.0 minutes, one eligible household-day, one false alert. Match `E-HELD-LEAK-P` 2026-06-15T10:00:00-07:00 to alarm 2026-06-15T10:15:00-07:00. Unmatched alarm 2026-06-15T08:15:00-07:00 through 2026-06-15T08:40:00-07:00 (irrigation). Unmatched event `E-HELD-LEAK-I`. Parameters 0.25 liters and 15 minutes, tuned on the train split only.
  - Competing alarms on one planted event score one true positive. A missing bucket prevents a 15-minute run from being filled in. Dropping readings after confirmation keeps the same alarm start.
- Artifact paths: `docs/evidence/p03/score.json`, `docs/evidence/p03/summary.txt`, `fixtures/oracle/heldout_persistence.md`
- Open issues: the comparison demo and HTML timeline are the next phase. Threshold results are covered by the tuner test (0.25 liters, 0 minutes) but not yet in the user report.
- Next phase: P04

## P04 — Ship the user workflow and reports

- Phase and status: PASS
- Files changed: `src/waterlens/report.py`, `src/waterlens/workflow.py`, `src/waterlens/cli.py`, `tests/test_demo.py`, `README.md`, `.gitignore`, `docs/evidence/p04/`, `docs/grokbot-progress.md`
- Commands and results:
  - `PYTHONPATH=src python -m pytest` → 17 passed.
  - `PYTHONPATH=src python -m waterlens --help` → exit 0. Commands listed: validate, evaluate, demo, score.
  - `PYTHONPATH=src python -m waterlens demo --output docs/evidence/p04` → exit 0. Persistence precision 0.5, recall 0.5, median delay 15.0 minutes, 1.0 false alerts per eligible household-day. Threshold precision 0.3333333333333333 (2/6), recall 1.0, median delay 0.0, 4 false alerts. Timeline CSV has 288 rows.
  - `PYTHONPATH=src python -m waterlens score --fixture fixtures/invalid --alarms fixtures/heldout/events.csv --output /tmp/bad-score` → exit 2. Message names `volume_liters` and row 3.
  - Browser check of `docs/evidence/p04/report.html` at 390px width: skip link is the first tab stop, shows a solid focus outline, and Enter moves the URL to `#timeline`. The status region reads the persistence and threshold figures. Page scroll width stays within the viewport. The only earlier console error was a missing favicon; the report now uses an empty icon link.
- Artifact paths: `docs/evidence/p04/report.html`, `docs/evidence/p04/summary.txt`, `docs/evidence/p04/score.json`, `docs/evidence/p04/timeline.csv`
- Open issues: performance budget, dependency review, and the validation write-up are the next phase.
- Next phase: P05

## P05 — Verify correctness, security, and performance

- Phase and status: PASS
- Files changed: `docs/validation.md`, `tests/test_harden.py`, `src/waterlens/report.py`, `pyproject.toml`, `docs/grokbot-progress.md`
- Commands and results:
  - `python -m compileall -q src tests` completed with no output.
  - `PYTHONPATH=src python -m pytest` → 21 passed.
  - Fresh `run_demo` on this host: 0.0226 seconds. Budget is 5 seconds. Held-out readings are 16,771 bytes.
  - OSV on 2026-11-23: pytest 9.2.0 has 0 vulnerabilities. setuptools 84.2.1 has 0. setuptools 68.1.2, already on the image, has 7, so the build backend is pinned to 84.2.1. `pip-audit` could not create a virtual environment because `python3-venv` is not installed; the OSV queries are the advisory check.
  - A defect found in this phase: scoring an external alarm file crashed the text summary because `parameters` is null. The summary now explains that the alarms came from a file. The new test scores `alarms_persistence.csv` and still gets precision 0.5, recall 0.5, and a 15-minute delay.
- Artifact paths: `docs/validation.md`
- Open issues: release notes, security contact, and the GitHub Actions workflow are the next phase. Hosted CI is P07.
- Next phase: P06

## P06 — Prepare a reproducible open-source release

- Phase and status: PASS
- Files changed: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `requirements-dev.txt`, `.github/workflows/ci.yml`, `pyproject.toml`, `docs/grokbot-progress.md`
- Commands and results:
  - Clean copy in `/tmp/waterlens-clean` followed the README: venv, `pip install -r requirements-dev.txt --require-hashes`, `pip install -e . --no-deps`, `pytest` (21 passed), `python -m waterlens demo --output out/demo`. Persistence precision 0.5, recall 0.5, median delay 15, false alerts per eligible household-day 1.
  - The first editable install failed because setuptools 84.2.1 rejects a license classifier next to `license = "MIT"`. The classifier was removed and the clean-room install then succeeded.
  - Wheel `waterlens-0.1.0-py3-none-any.whl` contains the `waterlens` modules and `licenses/LICENSE`. It does not contain fixtures, tests, or bytecode. Installed into a fresh virtual environment with `PYTHONPATH` unset, `python -m waterlens demo` reproduced the same persistence score.
  - Search of the tree found no private keys, `.env` files, or embedded tokens. Fixture manifests state the MIT terms and that the rows are synthetic.
- Artifact paths: `requirements-dev.txt`, `.github/workflows/ci.yml`, `/tmp/waterlens-wheel/waterlens-0.1.0-py3-none-any.whl` (local build, not committed)
- Open issues: hosted GitHub Actions has not run yet. That is P07.
- Next phase: P07
