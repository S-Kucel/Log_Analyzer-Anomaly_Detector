import csv
import json
import subprocess
import sys

import pytest

from log_analyzer.cli import main


def test_json_report_contains_summary_metadata_and_anomalies(example_dir, tmp_path, capsys):
    output = tmp_path / "reports" / "analysis.json"
    assert main([str(example_dir / "server.log"), "--output", str(output)]) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["summary"]["total_events"] == 425
    assert report["summary"]["levels"] == {"DEBUG": 0, "INFO": 340, "WARNING": 37, "ERROR": 48, "CRITICAL": 0}
    assert len(report["anomalies"]) == 4
    assert report["detector"]["window_minutes"] == 5
    assert "Detected anomalies: 4" in capsys.readouterr().out


def test_csv_bundle_contains_filtered_events_and_statistics(example_dir, tmp_path):
    output = tmp_path / "filtered.csv"
    assert main([str(example_dir / "server.csv"), "--level", "error", "--output", str(output)]) == 0
    with output.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 48
    assert {row["level"] for row in rows} == {"ERROR"}
    with output.with_name("filtered.summary.csv").open(encoding="utf-8", newline="") as handle:
        metrics = {row["metric"]: row["value"] for row in csv.DictReader(handle)}
    assert metrics["total_events"] == "48"
    assert output.with_name("filtered.anomalies.csv").is_file()


@pytest.mark.parametrize("strict", [False, True])
def test_invalid_records_are_reported_and_strict_mode_fails(tmp_path, strict, capsys):
    source = tmp_path / "input.log"
    source.write_text("broken\n2026-09-30 12:00:00 INFO OK\n", encoding="utf-8")
    output = tmp_path / "report.json"
    args = [str(source), "--output", str(output)] + (["--strict"] if strict else [])
    assert main(args) == (2 if strict else 0)
    assert output.exists() is not strict
    assert "Line 1" in capsys.readouterr().err
    if not strict:
        assert json.loads(output.read_text())["input"]["rejected_records"] == 1


def test_no_valid_records_fails(tmp_path):
    path = tmp_path / "invalid.log"
    path.write_text("broken\n", encoding="utf-8")
    assert main([str(path)]) == 2


@pytest.mark.parametrize("source_name", ["report.csv", "report.summary.csv", "report.anomalies.csv"])
def test_export_cannot_overwrite_source_or_companion_source(tmp_path, source_name):
    source = tmp_path / source_name
    content = "timestamp,level,message\n2026-09-30,INFO,Keep me\n"
    source.write_text(content, encoding="utf-8")
    assert main([str(source), "--output", str(tmp_path / "report.csv")]) == 2
    assert source.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("empty", [False, True])
def test_png_export_with_and_without_matches(example_dir, tmp_path, monkeypatch, empty):
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    output = tmp_path / "activity.png"
    args = [str(example_dir / "server.log"), "--plot", str(output)]
    if empty:
        args += ["--contains", "no such message"]
    assert main(args) == 0
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert output.stat().st_size > 1000


def test_missing_input_returns_clean_error(tmp_path, capsys):
    assert main([str(tmp_path / "missing.log")]) == 2
    assert "Error:" in capsys.readouterr().err


def test_python_module_entrypoint():
    result = subprocess.run([sys.executable, "-m", "log_analyzer", "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "--login-threshold" in result.stdout
