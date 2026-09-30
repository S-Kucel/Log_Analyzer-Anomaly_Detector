from datetime import datetime, timedelta

import pytest

from log_analyzer.anomalies import DetectorConfig, detect_anomalies
from log_analyzer.parser import read_logs


def window_rows(counts, level="INFO", message="Request"):
    start = datetime(2026, 9, 30, 12)
    return [(start + timedelta(minutes=5 * index, seconds=second), level, message)
            for index, count in enumerate(counts) for second in range(count)]


def test_demo_detects_known_anomalies_including_overlapping_rules(example_dir):
    events = read_logs(example_dir / "server.log").events
    anomalies = detect_anomalies(events)
    assert [(item["type"], item["count"], item["start"]) for item in anomalies] == [
        ("failed_logins", 25, "2026-09-30T12:30:00+00:00"),
        ("error_spike", 41, "2026-09-30T13:00:00+00:00"),
        ("activity_spike", 52, "2026-09-30T13:00:00+00:00"),
        ("activity_spike", 112, "2026-09-30T13:30:00+00:00"),
    ]


def test_stable_load_does_not_trigger_alerts(make_events):
    assert detect_anomalies(make_events(window_rows([60] * 16))) == []


def test_baseline_excludes_current_and_future_windows(make_events):
    rows = window_rows([1, 1, 1, 20], level="ERROR")
    before = detect_anomalies(make_events(rows))
    after = detect_anomalies(make_events(rows + window_rows([0, 0, 0, 0, 100], level="ERROR")))
    assert before[0]["type"] == "error_spike"
    assert before[0]["baseline_mean"] == 1
    assert before[0]["threshold"] == 10
    assert before[0] == after[0]


def test_insufficient_history_does_not_trigger_statistical_alerts(make_events):
    assert detect_anomalies(make_events(window_rows([60, 60], level="ERROR"))) == []


def test_empty_windows_are_part_of_baseline(make_events):
    events = make_events(window_rows([1, 0, 0, 10], level="CRITICAL"))
    anomalies = detect_anomalies(events)
    assert anomalies[0]["type"] == "error_spike"
    assert anomalies[0]["baseline_mean"] == pytest.approx(1 / 3)


def test_login_threshold_is_inclusive_and_windows_do_not_overlap(make_events):
    rows = window_rows([9, 10], level="WARNING", message="Authentication failed")
    anomalies = detect_anomalies(make_events(rows))
    assert len(anomalies) == 1
    assert anomalies[0]["count"] == 10
    assert anomalies[0]["start"] == "2026-09-30T12:05:00+00:00"
    assert anomalies[0]["end"] == "2026-09-30T12:10:00+00:00"


def test_successful_logins_are_not_failures(make_events):
    events = make_events(window_rows([20], message="Login successful"))
    assert detect_anomalies(events) == []


@pytest.mark.parametrize("options", [{"window_minutes": 0}, {"login_threshold": -1},
    {"baseline_windows": 2}, {"spike_factor": 1}, {"sigma": float("nan")}])
def test_invalid_detector_settings_are_rejected(options):
    with pytest.raises(ValueError):
        DetectorConfig(**options)
