from datetime import datetime, timedelta, timezone

import pytest

from log_analyzer.parser import parse_timestamp, read_logs


@pytest.mark.parametrize("fraction,microsecond", [
    ("1", 100000), ("12", 120000), ("125", 125000),
    ("0125", 12500), ("00125", 1250), ("000125", 125),
])
@pytest.mark.parametrize("decimal_separator", [".", ","])
@pytest.mark.parametrize("time_separator", ["T", " "])
@pytest.mark.parametrize("suffix,offset_minutes", [
    ("", 0), ("Z", 0), ("+02:00", 120), ("-05:30", -330),
])
def test_timestamp_normalizes_fractional_seconds(
    fraction, microsecond, decimal_separator, time_separator, suffix, offset_minutes,
):
    value = f"2026-09-30{time_separator}12:30:00{decimal_separator}{fraction}{suffix}"
    expected = datetime(2026, 9, 30, 12, 30, microsecond=microsecond, tzinfo=timezone.utc)
    expected -= timedelta(minutes=offset_minutes)
    assert parse_timestamp(value).isoformat() == expected.isoformat()


@pytest.mark.parametrize("fraction,microsecond", [
    ("1", 100000), ("12", 120000), ("125", 125000),
    ("0125", 12500), ("00125", 1250), ("000125", 125),
])
@pytest.mark.parametrize("separator", [".", ","])
@pytest.mark.parametrize("extension", ["log", "csv"])
def test_log_and_csv_preserve_fractional_seconds(tmp_path, fraction, microsecond, separator, extension):
    path = tmp_path / f"server.{extension}"
    timestamp = f"2026-09-30 14:30:00{separator}{fraction}+02:00"
    if extension == "csv":
        content = f'timestamp,level,message\n"{timestamp}",INFO,OK\n'
    else:
        content = f"{timestamp} INFO OK\n"
    path.write_text(content, encoding="utf-8")

    result = read_logs(path)

    assert not result.issues
    assert len(result.events) == 1
    expected = datetime(2026, 9, 30, 12, 30, microsecond=microsecond, tzinfo=timezone.utc)
    assert result.events.iloc[0]["timestamp"].isoformat() == expected.isoformat()


@pytest.mark.parametrize("fraction", ["", "1234567"])
@pytest.mark.parametrize("separator", [".", ","])
def test_log_rejects_invalid_fraction_lengths(tmp_path, fraction, separator):
    path = tmp_path / "server.log"
    path.write_text(f"2026-09-30 12:30:00{separator}{fraction}Z INFO Invalid\n", encoding="utf-8")

    result = read_logs(path)

    assert result.events.empty
    assert [issue.line for issue in result.issues] == [1]


def test_log_normalizes_timezones_levels_and_sorts(tmp_path):
    path = tmp_path / "server.log"
    path.write_text(
        "\ufeff2026-09-30 14:00:00+02:00 [warn] Slow request\n"
        "2026-09-30T11:00:00.250Z ERROR Database timeout\n"
        "2026-09-30 12:30:00,125 FATAL Connection lost\n\n",
        encoding="utf-8",
    )
    result = read_logs(path)
    assert not result.issues
    assert list(result.events["level"]) == ["ERROR", "WARNING", "CRITICAL"]
    assert result.events.iloc[1]["timestamp"].isoformat() == "2026-09-30T12:00:00+00:00"
    assert result.events.iloc[2]["timestamp"].microsecond == 125000
    assert list(result.events["source_line"]) == [2, 1, 3]


def test_bad_records_are_reported_with_line_numbers(tmp_path):
    path = tmp_path / "bad.log"
    path.write_text(
        "not a log\n2026-02-30 10:00:00 INFO Invalid date\n"
        "2026-09-30 10:00:00 NOTICE Unsupported level\n"
        "2026-09-30 10:00:00 INFO OK\n", encoding="utf-8",
    )
    result = read_logs(path)
    assert len(result.events) == 1
    assert [issue.line for issue in result.issues] == [1, 2, 3]


def test_csv_handles_commas_and_multiline_messages(tmp_path):
    path = tmp_path / "server.csv"
    path.write_text(
        'timestamp,level,message\n2026-09-30T12:00:00Z,INFO,"Hello, world\nSecond line"\n',
        encoding="utf-8",
    )
    result = read_logs(path)
    assert result.events.iloc[0]["message"].splitlines() == ["Hello, world", "Second line"]
    assert not result.issues


@pytest.mark.parametrize("header", ["time,level,message", "timestamp,level,message,message", ""])
def test_csv_rejects_invalid_headers(tmp_path, header):
    path = tmp_path / "server.csv"
    path.write_text(header, encoding="utf-8")
    with pytest.raises(ValueError, match="headers"):
        read_logs(path)


def test_csv_reports_invalid_rows(tmp_path):
    path = tmp_path / "server.csv"
    path.write_text(
        "timestamp,level,message\n"
        "2026-09-30T12:00:00,INFO\n"
        "2026-09-30T12:00:00,INFO,Hello,extra\n"
        "2026-09-30T12:00:00,INFO,\n", encoding="utf-8",
    )
    result = read_logs(path)
    assert result.events.empty
    assert len(result.issues) == 3


def test_csv_rejects_unclosed_quotes(tmp_path):
    path = tmp_path / "server.csv"
    path.write_text('timestamp,level,message\n2026-09-30,INFO,"unfinished', encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed CSV"):
        read_logs(path)


@pytest.mark.parametrize("name,content", [("empty.log", "\n"), ("empty.csv", "timestamp,level,message\n")])
def test_empty_input_has_valid_frame(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    result = read_logs(path)
    assert result.events.empty
    assert not result.issues
    assert str(result.events["timestamp"].dt.tz) == "UTC"


def test_demo_formats_are_equivalent(example_dir):
    log = read_logs(example_dir / "server.log")
    csv = read_logs(example_dir / "server.csv")
    assert log.events.drop(columns="source_line").equals(csv.events.drop(columns="source_line"))
    assert len(log.events) == 425
