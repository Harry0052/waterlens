import json
from pathlib import Path

from waterlens.cli import main
from waterlens.report import neutralize, render_html

ROOT = Path(__file__).resolve().parents[1]


def test_help_exits_zero(capsys) -> None:
    assert main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "validate" in captured.out
    assert "demo" in captured.out
    assert "score" in captured.out


def test_demo_writes_traceable_report(tmp_path: Path) -> None:
    output = tmp_path / "demo"
    assert main(["demo", "--output", str(output)]) == 0
    report = json.loads((output / "score.json").read_text(encoding="utf-8"))
    persistence = report["detectors"]["persistence"]
    threshold = report["detectors"]["threshold"]
    assert persistence["precision"] == 0.5
    assert persistence["recall"] == 0.5
    assert persistence["median_delay_minutes"] == 15
    assert persistence["false_alerts_per_eligible_household_day"] == 1
    assert threshold["precision"] == 2 / 6
    assert threshold["recall"] == 1
    assert threshold["median_delay_minutes"] == 0
    assert threshold["false_alerts"] == 4
    match = persistence["matches"][0]
    source = Path(match["source_readings"])
    assert source.is_file()
    text = source.read_text(encoding="utf-8")
    assert "2026-06-15T10:00:00-07:00" in text
    assert "0.4000" in text
    html = (output / "report.html").read_text(encoding="utf-8")
    assert 'lang="en"' in html
    assert 'href="#timeline"' in html
    assert 'role="status"' in html
    assert 'tabindex="0"' in html
    assert 'scope="col"' in html
    assert ":focus-visible" in html
    assert "@media (max-width: 40rem)" in html
    assert "E-HELD-LEAK-P" in html
    assert "E-HELD-IRR" in (output / "summary.txt").read_text(encoding="utf-8") or "08:15:00" in (
        output / "summary.txt"
    ).read_text(encoding="utf-8")
    assert "generated" in html.lower()


def test_malformed_score_explains_the_problem(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "score",
            "--fixture",
            str(ROOT / "fixtures" / "invalid"),
            "--alarms",
            str(ROOT / "fixtures" / "heldout" / "events.csv"),
            "--output",
            str(tmp_path / "bad"),
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["category"] == "value"
    assert "volume_liters" in payload["message"]
    assert "volume_liters" in captured.err


def test_partial_alarm_file_names_the_columns(tmp_path: Path, capsys) -> None:
    alarms = tmp_path / "alarms.csv"
    alarms.write_text("alarm_id,household_id\n", encoding="utf-8")
    code = main(
        [
            "score",
            "--fixture",
            str(ROOT / "fixtures" / "heldout"),
            "--alarms",
            str(alarms),
            "--output",
            str(tmp_path / "out"),
        ]
    )
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["category"] == "schema"
    assert "columns must be" in payload["message"]


def test_html_escapes_user_text_and_csv_neutralizes_formulas() -> None:
    report = {
        "detectors": {
            "persistence": {
                "precision": 0.5,
                "recall": 0.5,
                "median_delay_minutes": 15,
                "false_alerts_per_eligible_household_day": 1,
                "eligible_household_days": 1,
                "matches": [],
                "unmatched_alarms": [],
                "unmatched_events": [],
            }
        },
        "limitations": ["<script>alert(1)</script>"],
        "config_hashes": {"test": "abc"},
    }
    html = render_html(
        report,
        [
            {
                "household_id": "<img>",
                "timestamp": "t",
                "volume_liters": "0.0000",
                "events": "",
                "alarms": "",
                "notes": "<script>",
            }
        ],
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img&gt;" in html
    assert neutralize("=1+1") == "'=1+1"
    assert neutralize("0.4000") == "0.4000"
