# Overlap review

Access date for every source below: 2026-11-23.

Decision: **proceed**. No existing tool already scores the WaterLens acceptance case. WaterLens should be its own repository. Do not vendor pySIMDEUM or STREaM, and do not treat Flume Usage Alerts as an evaluation harness.

The shared comparison held one input, one artifact, and one metric constant:

- Input: one synthetic household, 5-minute interval volumes in liters, one planted persistent leak, one planted intermittent leak, and one sustained irrigation block. Timestamps carry explicit offsets.
- Artifact: an event-level score with precision, recall, median detection delay, and false alerts per eligible household-day, plus the matched event and alarm timestamps.
- Metric: event precision and recall on planted leaks only, with one-to-one credit for each planted event.

## Capability matrix

| Capability | pySIMDEUM 1.0.1 | STREaM (MATLAB) | Flume Usage Alerts | engdino/water-leak-detection | WaterLens MVP |
| --- | --- | --- | --- | --- | --- |
| Synthetic household interval trace | Yes, end-use demand | Yes, end-use demand | No | No (observed cumulative m³) | Yes, original generator |
| Planted leak labels | No | No | No | No | Yes |
| Event precision and recall | No | No | No | No | Yes |
| Detection delay | No | No | No | No | Yes |
| False alerts per household-day | No | No | No | No | Yes |
| Irrigation false-alarm case | Irrigation is not a labeled end use in the published API | Fixtures listed do not include irrigation | Product can ignore irrigation; not a scored fixture | No labels | Yes |
| Score an external alarm file | No | No | No | No | Yes |
| Train/test household isolation | No | No | No | No | Yes |
| Runs on this machine without a paid license | Import succeeded; simulation failed | MATLAB and Octave are absent | Proprietary app, no local API | Data has no license | Python 3.11+ standard library |

## Probes

### pySIMDEUM

- Primary URL: https://github.com/KWR-Water/pysimdeum
- Package: https://pypi.org/project/pysimdeum/1.0.1/
- Version probed: PyPI `1.0.1` (`__version__ == "1.0.1"`)
- Master commit inspected, not executed: `e489718c6a6e6f8697a627b483553f3e59c2f78e` (2026-06-12, "Consumption icm")
- Release tag on GitHub for 1.0.1: `d1209e3` (2024-08-26)
- License: EUPL-1.2. The EUPL compatibility appendix lists GPL, AGPL, LGPL, MPL, OSL, EPL, CeCILL, CC BY-SA 3.0 (non-software), LiLiQ, and EUPL. It does not list MIT. Copying the generator into this MIT repository would be a license problem.
- Dataset terms: Dutch household statistics ship inside the package. They are model inputs, not leak ground truth. A worldwide review is cited from the README (Mazzoni et al., Water Research, 2022) and was not copied.
- Evidence kind: **observed run** plus **documentation**.
- Observed commands and results:
  - `python3 -m pip install --target /tmp/p01-py pysimdeum==1.0.1` completed.
  - Public names on the installed package: `api`, `built_house`, `core`, `data`.
  - A scan of the installed `*.py` tree for `precision`, `recall`, `false alarm`, `leak`, `alarm`, `ground truth`, and `ground_truth` returned no hits.
  - `built_house()` in 1.0.1 takes only `house_type` and always calls `simulate(num_patterns=100)`.
  - Constructing a one-person house and calling `simulate(num_patterns=1, duration="1 day")` failed before any trace was produced: `ValueError: Invalid frequency: 1H` from `pandas.timedelta_range(..., freq="1H")` under pandas 3.1.1, numpy 2.5.5, xarray 2026.9.0, Python 3.12.3. The published wheel does not emit the shared fixture on this host.
  - Master `pysimdeum/api.py` exposes `built_house` and `build_multi_hh` only. The master README describes end-use demand, discharge, CSV/Excel/NetCDF export, and plots. It does not describe leak injection or detector scoring.
- Features that already match: stochastic residential end-use demand, reproducible only to the extent the caller controls house type, and CSV export of demand. Those are generator features, not the acceptance artifact.
- Why not integrate or contribute first: the acceptance case needs planted-event labels, one-to-one alarm matching, and a frozen score. pySIMDEUM does not have that workflow. EUPL-1.2 is also a poor fit for an MIT benchmark that must stay runnable without the package.

### STREaM

- Primary URL: https://github.com/acominola/STREaM
- Commit: `6cf74074655bb677bb89b9a1e813b47da051ad77` (2019-02-07, "Update README.md")
- License: GPL-3.0
- Dataset terms: calibrated on observed, disaggregated end uses from more than 300 single-family households in nine U.S. cities (DeOreo, 2011). `database.mat` is part of the model. Those traces are not planted-leak labels, and this repository will not redistribute them.
- Requirements: MATLAB, tested by the authors on R2016a. `matlab` and `octave` are not installed here (`MATLAB_ABSENT`, `OCTAVE_ABSENT`).
- Evidence kind: **documentation**. The runtime check is unresolved because the required tool is missing. The README is specific enough that a shared-fixture score is not something the program claims to emit.
- Output the README actually names: `outputTrajectory.mat` with per-fixture consumption and the aggregate. End uses in this version: toilet, shower, faucet, clothes washer, dishwasher, bathtub. No leak event, no alarm file, no precision, no delay.
- Features that already match: synthetic residential end-use sequences at a chosen sampling interval, with a household-size parameter.
- Why not integrate: GPL-3 plus a MATLAB runtime would pull the benchmark off the MIT, standard-library path, and the model still would not score detectors. Contributing an evaluation harness to STREaM would change that project's purpose and license boundary. A separate scorer that can accept any CSV is the smaller contract.

### Flume Usage Alerts

- Primary URL: https://help.flumewater.com/en/articles/1548336-usage-alerts
- Version: help-center article "Usage Alerts", written by Joe Fazio, updated July 1, 2026. No software version is published on that page.
- License: proprietary product documentation. Not reusable as code or as a fixture.
- Evidence kind: **documentation**. There is no local API to run the shared fixture. An observed product run would need a Flume account and a physical meter. That is out of scope and was not attempted.
- Documented semantics:
  - Smart Leak Alert: continuous flow for 2 hours by default, and the article says the alert ignores irrigation.
  - High Flow Alert: at least 5 gallons per minute for 15 minutes.
  - Extra product behavior: Do Not Alert schedules, Expected Usage, and Away Mode.
- Features that already match: duration and flow thresholds, and an awareness that irrigation causes false alerts. Those are resident-notification controls. They are not event precision, recall, delay, or false alerts per eligible household-day on labeled traces.
- Why not treat this as the solution: the benchmark has to show where normal use triggers false alerts. Flume's documented smart alert is designed to hide irrigation. Copying that behavior would erase the comparison the MVP exists to measure.

### Closest discovery result

GitHub repository search on 2026-11-23 for `residential interval water meter leak detector benchmark household`, `SIMDEUM STREaM household water demand leak`, and `household water leak event precision recall detector benchmark` returned `total_count: 0` from the connected GitHub search. Web search on the playbook queries did return adjacent work.

Closest credible project: https://github.com/engdino/water-leak-detection

- Pushed: 2021-03-20. License field: null. Stars at access time: 1.
- Evidence kind: **documentation** (README). The JSON files were not downloaded. They are described as real apartment meters, and the playbook forbids bundling household exports.
- Contents: 15-minute cumulative cubic-meter readings for 8 apartments, 2019–2020. No leak-event labels, no detector, no score file.
- Other public work that does not meet the case:
  - GST4Water day-level minimum-night-flow flags (https://www.mdpi.com/2073-4441/11/3/405). Precision is reported for a day classifier (0.73 for the 02:00–05:00 window). Irrigation is discussed as a false-alarm source. There is no reusable event-episode harness and no synthetic planted-leak fixture.
  - KIOS LeakDB (https://github.com/kios-research/leakdb) is a district-network benchmark, not a single household interval meter.
  - Academic intra-domestic sets label whole days, not alarm episodes with a detection delay.

MachineSight is named in the playbook as a different problem (reconciling two simultaneous sources). Repository search for `MachineSight water meter readings` returned no public repository. It is not a contender for this acceptance case.

## Remaining uncertainties

- pySIMDEUM master might simulate on an older pandas that still accepts `freq="1H"`. That would still produce unlabeled demand, not the score artifact. Not re-probed with a pandas downgrade.
- STREaM was not executed. The missing tool is MATLAB or a compatible Octave port. The README output contract is enough to reject it for the acceptance artifact.
- Flume's production model may differ from the help-center defaults. The page is the behavior the vendor documents. It is not a benchmark.
- GitHub code search for the words `leak` and `precision` inside the two simulator repositories returned no hits. The same search endpoint returned no hits for broader benchmark queries, so an empty code search is weak evidence on its own. The README, API file, and installed-tree scan are the evidence used here.
- No paper found in the playbook queries publishes the exact frozen case (precision 0.5, recall 0.5, 15-minute delay, one irrigation false alarm, one missed intermittent leak) as a reusable fixture.

## Decision

Proceed with a small MIT benchmark that generates its own labeled interval traces and scores two baseline detectors. Do not wrap pySIMDEUM, STREaM, or Flume. Contribution to those projects would not satisfy the acceptance case, because the case is an evaluation report rather than a demand simulator or a resident alert.
