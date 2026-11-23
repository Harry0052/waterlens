"""Human and machine reports. User text is escaped or neutralized before it is written."""

from __future__ import annotations

import csv
import html
import io
from datetime import datetime, timezone

from waterlens.models import ALARM_COLUMNS, READING_COLUMNS, Alarm, Event, Fixture, Reading
from waterlens.score import _stamp

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def neutralize(value: object) -> str:
    text = str(value)
    if text.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def escape_text(value: object) -> str:
    return html.escape(str(value), quote=True)


def comparison_summary(report: dict) -> str:
    lines = [
        "WaterLens comparison",
        "Measurements in this report are generated.",
        f"Train households: {', '.join(report['train_households'])}",
        f"Test households: {', '.join(report['test_households'])}",
        f"Configuration hashes: {report['config_hashes']}",
        "",
    ]
    for name, section in report["detectors"].items():
        lines.append(f"Detector {name}")
        if section.get("parameters"):
            lines.append(
                "  Parameters: flow "
                f"{section['parameters']['flow_threshold_liters']} liters per interval, "
                f"persistence {section['parameters']['persistence_minutes']} minutes"
            )
        else:
            lines.append("  Parameters: alarms were supplied in a file and were not produced by a tuned baseline.")
        lines.append(f"  Precision: {section['precision']}")
        lines.append(f"  Recall: {section['recall']}")
        lines.append(f"  Median detection delay: {section['median_delay_minutes']} minutes")
        lines.append(
            "  False alerts per eligible household-day: "
            f"{section['false_alerts_per_eligible_household_day']} "
            f"({section['false_alerts']} unmatched alarms / {section['eligible_household_days']} eligible days)"
        )
        lines.append("  Matched events:")
        for match in section["matches"]:
            lines.append(
                f"    {match['event_id']} {match['event_start']} matched {match['alarm_id']} "
                f"at {match['alarm_start']} (delay {match['delay_minutes']} minutes). "
                f"Source readings: {match['source_readings']}"
            )
        lines.append("  Unmatched alarms:")
        for alarm in section["unmatched_alarms"]:
            lines.append(f"    {alarm['alarm_id']} {alarm['alarm_start']} to {alarm['alarm_end']}")
        lines.append("  Unmatched planted events:")
        for event in section["unmatched_events"]:
            lines.append(f"    {event['event_id']} {event['event_start']} to {event['event_end']}")
        if section["excluded_household_days"]:
            lines.append("  Excluded household-days:")
            for day in section["excluded_household_days"]:
                lines.append(
                    f"    {day['household_id']} {day['date']} coverage {day['coverage']} ({day['reason']})"
                )
        lines.append("")
    lines.append("Limitations:")
    lines.extend(f"- {item}" for item in report["limitations"])
    lines.append("")
    lines.append("Trace a row in report.html back to the timestamp in the held-out readings.csv named in the match.")
    return "\n".join(lines) + "\n"


def alarm_csv(alarms: list[Alarm], timezones: dict[str, str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(ALARM_COLUMNS)
    for alarm in alarms:
        zone_name = timezones[alarm.household_id]
        writer.writerow(
            [
                neutralize(alarm.alarm_id),
                neutralize(alarm.household_id),
                neutralize(alarm.detector_id),
                _stamp(alarm.start, zone_name),
                _stamp(alarm.end, zone_name),
                neutralize(alarm.provenance),
            ]
        )
    return buffer.getvalue()


def build_timeline(fixture: Fixture, alarms: list[Alarm]) -> list[dict]:
    events_by_household: dict[str, list[Event]] = {}
    for event in fixture.events:
        events_by_household.setdefault(event.household_id, []).append(event)
    rows: list[dict] = []
    for reading in fixture.readings:
        zone_name = fixture.timezone_for(reading.household_id)
        event_ids = [
            event.event_id
            for event in events_by_household.get(reading.household_id, [])
            if event.start <= reading.start < event.end
        ]
        alarm_ids = [
            alarm.alarm_id
            for alarm in alarms
            if alarm.household_id == reading.household_id and alarm.start <= reading.start < alarm.end
        ]
        rows.append(
            {
                "household_id": reading.household_id,
                "timestamp": reading.timestamp_text,
                "utc": reading.start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "volume_liters": f"{reading.volume_liters:.4f}",
                "events": " ".join(event_ids),
                "alarms": " ".join(alarm_ids),
                "notes": "generated",
                "sort": reading.start,
            }
        )
    for missing in fixture.missing_intervals:
        rows.append(
            {
                "household_id": missing["household_id"],
                "timestamp": missing["start"],
                "utc": missing["start"],
                "volume_liters": "",
                "events": "",
                "alarms": "",
                "notes": "missing interval; not interpolated; excluded from detector evidence",
                "sort": datetime.fromisoformat(missing["start"].replace("Z", "+00:00")),
            }
        )
    rows.sort(key=lambda item: (item["household_id"], item["sort"], item["timestamp"]))
    return rows


def timeline_csv(rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    header = ["household_id", "timestamp", "volume_liters", "events", "alarms", "notes"]
    writer.writerow(header)
    for row in rows:
        writer.writerow(
            [
                neutralize(row["household_id"]),
                neutralize(row["timestamp"]),
                row["volume_liters"],
                neutralize(row["events"]),
                neutralize(row["alarms"]),
                neutralize(row["notes"]),
            ]
        )
    return buffer.getvalue()


def render_html(report: dict, rows: list[dict]) -> str:
    status_bits = []
    for name, section in report["detectors"].items():
        status_bits.append(
            f"{name} precision {section['precision']}, recall {section['recall']}, "
            f"median delay {section['median_delay_minutes']} minutes, "
            f"false alerts per eligible household-day {section['false_alerts_per_eligible_household_day']}"
        )
    status = ". ".join(status_bits) + "."
    metric_rows = []
    for name, section in report["detectors"].items():
        metric_rows.append(
            "<tr>"
            f"<td>{escape_text(name)}</td>"
            f"<td>{escape_text(section['precision'])}</td>"
            f"<td>{escape_text(section['recall'])}</td>"
            f"<td>{escape_text(section['median_delay_minutes'])}</td>"
            f"<td>{escape_text(section['false_alerts_per_eligible_household_day'])}</td>"
            f"<td>{escape_text(section['eligible_household_days'])}</td>"
            "</tr>"
        )
    finding_rows = []
    for name, section in report["detectors"].items():
        for match in section["matches"]:
            finding_rows.append(
                "<tr>"
                f"<td>{escape_text(name)}</td>"
                f"<td>match</td>"
                f"<td>{escape_text(match['event_id'])}</td>"
                f"<td>{escape_text(match['event_start'])}</td>"
                f"<td>{escape_text(match['alarm_id'])} {escape_text(match['alarm_start'])}</td>"
                f"<td>{escape_text(match['source_readings'])}</td>"
                "</tr>"
            )
        for alarm in section["unmatched_alarms"]:
            finding_rows.append(
                "<tr>"
                f"<td>{escape_text(name)}</td>"
                f"<td>unmatched alarm</td>"
                f"<td></td>"
                f"<td></td>"
                f"<td>{escape_text(alarm['alarm_id'])} {escape_text(alarm['alarm_start'])} to {escape_text(alarm['alarm_end'])}</td>"
                f"<td>{escape_text(alarm['source_readings'])}</td>"
                "</tr>"
            )
        for event in section["unmatched_events"]:
            finding_rows.append(
                "<tr>"
                f"<td>{escape_text(name)}</td>"
                f"<td>unmatched event</td>"
                f"<td>{escape_text(event['event_id'])}</td>"
                f"<td>{escape_text(event['event_start'])}</td>"
                f"<td></td>"
                f"<td>{escape_text(event['source_readings'])}</td>"
                "</tr>"
            )
    body_rows = []
    for row in rows:
        body_rows.append(
            "<tr>"
            f"<td>{escape_text(row['household_id'])}</td>"
            f"<td>{escape_text(row['timestamp'])}</td>"
            f"<td>{escape_text(row['volume_liters'])}</td>"
            f"<td>{escape_text(row['events'])}</td>"
            f"<td>{escape_text(row['alarms'])}</td>"
            f"<td>{escape_text(row['notes'])}</td>"
            "</tr>"
        )
    limitations = "".join(f"<li>{escape_text(item)}</li>" for item in report["limitations"])
    hashes = "".join(
        f"<li>{escape_text(key)}: {escape_text(value)}</li>" for key, value in report["config_hashes"].items()
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="data:,">
  <title>WaterLens comparison</title>
  <style>
    :focus-visible {{ outline: 3px solid #0b5fff; outline-offset: 2px; }}
    body {{ margin: 1rem; font-family: sans-serif; line-height: 1.4; }}
    p, li, h1, h2, caption {{ overflow-wrap: anywhere; }}
    .table-wrap {{
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      overflow-x: auto;
      max-width: 100%;
    }}
    table {{ border-collapse: collapse; width: max-content; min-width: 100%; }}
    th, td {{ border: 1px solid #999; padding: 0.3rem 0.5rem; text-align: left; vertical-align: top; }}
    caption {{ caption-side: top; text-align: left; font-weight: bold; margin-bottom: 0.4rem; white-space: normal; }}
    @media (max-width: 40rem) {{
      body {{ margin: 0.5rem; }}
      h1 {{ font-size: 1.4rem; }}
    }}
  </style>
</head>
<body>
  <a href="#timeline">Skip to the time-series table</a>
  <h1>WaterLens comparison</h1>
  <p>Units: liters per 5-minute interval. Delays are minutes. All volumes below are generated.</p>
  <div role="status" aria-live="polite">{escape_text(status)}</div>
  <h2>Coverage, delay, and false alerts</h2>
  <div class="table-wrap" tabindex="0" aria-label="Detector metrics">
    <table>
      <caption>Event scores on held-out households. False alerts use eligible household-days only.</caption>
      <thead>
        <tr>
          <th scope="col">Detector</th>
          <th scope="col">Precision</th>
          <th scope="col">Recall</th>
          <th scope="col">Median delay (minutes)</th>
          <th scope="col">False alerts per eligible household-day</th>
          <th scope="col">Eligible household-days</th>
        </tr>
      </thead>
      <tbody>
        {''.join(metric_rows)}
      </tbody>
    </table>
  </div>
  <h2>Matched and unmatched events</h2>
  <div class="table-wrap" tabindex="0">
    <table>
      <caption>One-to-one matches. An unmatched alarm did not receive credit for a planted leak.</caption>
      <thead>
        <tr>
          <th scope="col">Detector</th>
          <th scope="col">Kind</th>
          <th scope="col">Event</th>
          <th scope="col">Event start</th>
          <th scope="col">Alarm</th>
          <th scope="col">Source readings</th>
        </tr>
      </thead>
      <tbody>
        {''.join(finding_rows)}
      </tbody>
    </table>
  </div>
  <h2 id="timeline">Time series</h2>
  <div class="table-wrap" tabindex="0" aria-label="Interval timeline">
    <table>
      <caption>Generated interval timeline for the scored households. Empty volume means the interval was missing and was not interpolated.</caption>
      <thead>
        <tr>
          <th scope="col">Household</th>
          <th scope="col">Timestamp</th>
          <th scope="col">Liters</th>
          <th scope="col">Events</th>
          <th scope="col">Alarms</th>
          <th scope="col">Notes</th>
        </tr>
      </thead>
      <tbody>
        {''.join(body_rows)}
      </tbody>
    </table>
  </div>
  <h2>Provenance</h2>
  <ul>{hashes}</ul>
  <h2>Limitations</h2>
  <ul>{limitations}</ul>
</body>
</html>
"""


def reading_header() -> list[str]:
    return list(READING_COLUMNS)
