# Validation

Access date: 2026-11-23. The checks below are on the synthetic fixtures in this repository. There is no external household dataset and no hardware demo.

## Environment

- Python 3.12.3 (GCC 13.3.0), Linux 6.12.113+ x86_64, glibc 2.39
- Runtime dependencies: none
- Tests: pytest 9.2.0, MIT (`License-Expression: MIT`)
- Build backend pin: setuptools 84.2.1
- Host demo timing: 0.0226 seconds for `run_demo` on a fresh temporary directory
- Held-out readings file: 16,771 bytes. Held-out events file: 578 bytes. Demo HTML report: about 40 KB.

## Performance budget

The supported demo is two generated household-days at a 5-minute interval, two baselines, and one HTML report. Budget: under 5 seconds on an ordinary developer machine, measured around the demo call and excluding install time. Observed: 0.0226 seconds. `tests/test_harden.py` repeats the demo in a fresh directory and fails if it takes 5 seconds or longer. The second run in that test matches the first run's precision and recall.

## Acceptance evidence

Tolerance is exact equality. The rules are counts and minute differences on generated intervals, not a fitted model.

| Check | Expected | Where it was observed |
| --- | --- | --- |
| Persistence precision, recall, median delay | 0.5, 0.5, 15 minutes | `tests/test_score.py` against `fixtures/oracle/heldout_persistence.json`; demo report |
| Irrigation false alarm | one unmatched alarm 08:15–08:40 | same oracle and `docs/evidence/p04/summary.txt` |
| Missed intermittent leak | `E-HELD-LEAK-I` unmatched | same |
| One planted event, two overlapping alarms | 1 true positive, not 2 | `test_competing_alarms_score_one_event_once` |
| Held-out edits do not retune | parameters stay 0.25 L and 15 minutes | `test_heldout_edits_do_not_change_training` |
| Exact duplicate, conflicting duplicate, unsorted row, repeated local hour, missing interval | 2 duplicates ignored, 1 conflict quarantined, UTC order on the fold, 1 missing interval | `tests/test_validate.py` |
| Gap is not interpolated | a hole inside a 0.4 L run produces no 15-minute alarm | `test_gap_breaks_persistence_and_is_not_interpolated` |
| No future reading moves the alarm start earlier | start stays at +15 minutes when later rows are removed | `test_alarm_start_does_not_use_future_readings` |
| Sparse day leaves the denominator | 10 of 288 slots, reason `insufficient_coverage` | `test_sparse_household_day_is_excluded` |
| External alarm CSV | persistence export scores 0.5 / 0.5 / 15 without executing the file | `test_exported_alarm_file_scores_without_being_executed` |
| Bad input | negative volume, exit 2, message names the field and row | `tests/test_demo.py` |

The held-out day has 287 of 288 slots, so it stays eligible. False alerts per eligible household-day for persistence is 1/1 = 1.

## Domain safeguards

- Training and test households are different ids and different days. `tune` receives only the train split.
- A persistence alarm opens at the first interval that is already 15 minutes into the current run. Later intervals can extend the end. They do not move the start earlier.
- A missing interval ends the run. Nothing is written into the hole.
- Household-days under 90 percent coverage are listed with `insufficient_coverage` and are not part of the false-alert denominator.
- Planted events with fewer than half of their slots observed are listed as unevaluable and are left out of precision and recall. The frozen events are fully observed.
- HTML text is escaped. CSV text cells that start with `=`, `+`, `-`, `@`, tab, or carriage return get a leading apostrophe.
- Reports say the volumes are generated.

## Trust boundaries

- Inputs are CSV and JSON. The program does not call `eval`, start a subprocess, or fetch data.
- Readings must say `provenance=generated`. Alarm files may say `generated` or `external`. An alarm file is parsed as rows. It is not imported as code.
- File size is limited to 20 MB and tables to 200,000 rows. Volumes must be finite and between 0 and 200 liters per interval. Years must be 2000 through 2100.
- Demo and external scoring write fixed names under the directory passed as `--output`. A relative name containing `..` is rejected.
- No credentials are read or stored.

## Dependency and license review

- OSV query on 2026-11-23 for PyPI `pytest` 9.2.0: 0 vulnerabilities.
- OSV query for PyPI `setuptools` 68.1.2 (the copy already on this image): 7 vulnerabilities, including GHSA-5rjg-fvgr-3xxf and GHSA-cx63-2mw6-8hw5. Those apply to setuptools' package download and install helpers, which the scorer does not call.
- OSV query for setuptools 84.2.1: 0 vulnerabilities. The build backend is pinned to that version so a wheel build does not float to the older copy.
- `pip-audit` could not be used as the primary check: it tried to create a virtual environment and this image does not have `python3-venv`. The OSV queries above are the advisory evidence.
- Project license is MIT. pytest is MIT. pySIMDEUM (EUPL-1.2) and STREaM (GPL-3.0) are not dependencies. See `docs/overlap.md`.

## Commands

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m pytest
PYTHONPATH=src python -m waterlens demo --output out/demo
PYTHONPATH=src python -m waterlens validate fixtures/invalid
```

`compileall` completed with no output. Full `pytest` after the fix below: 21 passed. The invalid fixture exits 2.

One defect showed up while scoring an exported alarm file: the text summary assumed every detector had tuned parameters and raised `TypeError` when `parameters` was null. External alarms have no tuned parameters. The summary now says the alarms came from a file, and `test_exported_alarm_file_scores_without_being_executed` covers that path.

## Residual limitations

- The score is only as meaningful as the generated schedule. It does not estimate performance on a real meter.
- The two baselines are reference rules. A file of external alarms can be scored, and that file can be wrong.
- One missing interval on the frozen day does not drop the day below 90 percent coverage. A larger outage does, and the report has to be read for the exclusion reason.
- setuptools advisories remain relevant for anyone who builds packages with an older setuptools than 84.2.1. The pinned build requirement is the mitigation in this repository.
