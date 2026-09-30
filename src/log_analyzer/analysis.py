"""Filtering and descriptive statistics, independent of the command line."""

import re

import pandas as pd

from log_analyzer.parser import LEVELS, parse_timestamp


def filter_events(
    events: pd.DataFrame,
    since: str | None = None,
    until: str | None = None,
    levels: list[str] | None = None,
    contains: str | None = None,
) -> pd.DataFrame:
    start = parse_timestamp(since) if since else None
    end = parse_timestamp(until) if until else None
    whole_end_day = bool(until and re.fullmatch(r"\d{4}-\d{2}-\d{2}", until))
    if whole_end_day:
        end += pd.Timedelta(days=1)
    if start is not None and end is not None:
        if start > end or (whole_end_day and start == end):
            raise ValueError("--since must not be later than --until")
    if levels and any(level not in LEVELS for level in levels):
        raise ValueError("Unknown filter level")

    mask = pd.Series(True, index=events.index)
    if start is not None:
        mask &= events["timestamp"] >= start
    if end is not None:
        mask &= events["timestamp"] < end if whole_end_day else events["timestamp"] <= end
    if levels:
        mask &= events["level"].isin(levels)
    if contains is not None:
        mask &= events["message"].str.contains(contains, case=False, regex=False, na=False)
    return events.loc[mask].copy()


def event_counts(events: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Count events and errors in UTC bins, including empty intervals."""
    if minutes <= 0:
        raise ValueError("Window size must be positive")
    if events.empty:
        return pd.DataFrame(columns=["events", "errors"])
    data = events.set_index("timestamp")
    flags = pd.DataFrame({
        "events": 1,
        "errors": data["level"].isin(["ERROR", "CRITICAL"]).astype(int),
    }, index=data.index)
    frequency = f"{minutes}min"
    # Guard against accidentally allocating millions of empty time bins.
    span = (data.index.max() - data.index.min()).total_seconds()
    if span / (minutes * 60) > 1_000_000:
        raise ValueError("Time range is too large; narrow it with --since/--until")
    return flags.resample(frequency, origin="epoch").sum()


def _most_common(messages: pd.Series, limit: int) -> list[dict]:
    return [
        {"message": str(message), "count": int(count)}
        for message, count in messages.value_counts().head(limit).items()
    ]


def summarize(events: pd.DataFrame, top: int = 5) -> dict:
    counts = events["level"].value_counts()
    errors = events[events["level"].isin(["ERROR", "CRITICAL"])]
    hourly = event_counts(events, 60)
    return {
        "total_events": len(events),
        "levels": {level: int(counts.get(level, 0)) for level in LEVELS},
        "time_range": {
            "start": events["timestamp"].min().isoformat() if not events.empty else None,
            "end": events["timestamp"].max().isoformat() if not events.empty else None,
        },
        "most_common_messages": _most_common(events["message"], top),
        "most_common_errors": _most_common(errors["message"], top),
        "hourly_counts": [
            {"start": stamp.isoformat(), "events": int(row["events"]), "errors": int(row["errors"])}
            for stamp, row in hourly.iterrows()
        ],
    }
