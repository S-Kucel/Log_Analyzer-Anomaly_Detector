import pytest

from log_analyzer.analysis import event_counts, filter_events, summarize


def test_date_filter_includes_entire_final_day(make_events):
    events = make_events([
        ("2026-09-29T23:59:59", "INFO", "Before"),
        ("2026-09-30T00:00:00", "INFO", "Start"),
        ("2026-09-30T23:59:59.999999", "ERROR", "End"),
        ("2026-10-01T00:00:00", "INFO", "After"),
    ])
    selected = filter_events(events, since="2026-09-30", until="2026-09-30")
    assert list(selected["message"]) == ["Start", "End"]
    assert len(events) == 4


def test_filters_combine_and_text_is_literal(make_events):
    events = make_events([
        ("2026-09-30T12:00:00", "ERROR", "DB [timeout]"),
        ("2026-09-30T12:00:01", "INFO", "DB [timeout]"),
        ("2026-09-30T12:00:02", "ERROR", "DB timeout"),
    ])
    selected = filter_events(events, since="2026-09-30T14:00:00+02:00",
                             until="2026-09-30T12:00:00Z", levels=["ERROR"], contains="[TIMEOUT]")
    assert len(selected) == 1
    assert selected.iloc[0]["message"] == "DB [timeout]"


@pytest.mark.parametrize("since,until", [("2026-10-02", "2026-10-01"), ("2026-10-02T01:00:00", "2026-10-02T00:00:00")])
def test_reversed_dates_fail(make_events, since, until):
    with pytest.raises(ValueError, match="--since"):
        filter_events(make_events([]), since=since, until=until)


def test_summary_counts_critical_errors_and_empty_hours(make_events):
    events = make_events([
        ("2026-09-30T12:00:00", "INFO", "OK"),
        ("2026-09-30T14:00:00", "ERROR", "Database timeout"),
        ("2026-09-30T14:00:00", "CRITICAL", "Database timeout"),
    ])
    summary = summarize(events)
    assert summary["total_events"] == 3
    assert summary["levels"]["WARNING"] == 0
    assert summary["most_common_errors"] == [{"message": "Database timeout", "count": 2}]
    assert [hour["events"] for hour in summary["hourly_counts"]] == [1, 0, 2]
    assert summary["hourly_counts"][2]["errors"] == 2


def test_empty_selection_has_zero_statistics(make_events):
    events = filter_events(make_events([]), contains="missing")
    summary = summarize(events)
    assert summary["total_events"] == 0
    assert summary["time_range"] == {"start": None, "end": None}
    assert not summary["hourly_counts"]


def test_excessive_time_range_is_rejected_before_resampling(make_events):
    events = make_events([("1900-01-01", "INFO", "A"), ("2100-01-01", "INFO", "B")])
    with pytest.raises(ValueError, match="Time range"):
        event_counts(events, 5)
