# Grokbot progress

Index

| Phase | Status | Next |
| --- | --- | --- |
| P01 | PASS | P02 |
| P02 | not started | |
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
