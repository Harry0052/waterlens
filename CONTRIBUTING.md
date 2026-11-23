# Contributing

WaterLens scores generated household interval traces. Changes should keep that boundary.

- Use Python 3.11 or newer.
- Install from `requirements-dev.txt` and run `python -m pytest`.
- Keep new fixtures synthetic. Do not add measured household exports, account data, or credentials.
- Do not add a dependency on pySIMDEUM or STREaM. Their licenses and outputs are described in `docs/overlap.md`.
- Tune detectors only on the train split. Held-out households are for scoring.
- User-controlled text that reaches HTML must be escaped. Text written to CSV must be neutralized when it could be a spreadsheet formula.
- Prefer a small change with a test that names the expected count or timestamp.

Open a pull request against `main`. Do not merge it yourself if branch protection requires a review.
