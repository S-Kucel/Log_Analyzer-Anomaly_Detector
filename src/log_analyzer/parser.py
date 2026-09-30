"""Read supported log formats and keep track of rejected records."""

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_ALIASES = {"WARN": "WARNING", "FATAL": "CRITICAL"}
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:[.,]\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?)\s+"
    r"(?:\[(?P<bracket_level>[A-Za-z]+)\]|(?P<level>[A-Za-z]+))"
    r"\s+(?P<message>.+)$"
)


@dataclass(frozen=True)
class ParseIssue:
    line: int
    reason: str


@dataclass
class ParseResult:
    events: pd.DataFrame
    issues: list[ParseIssue]


def parse_timestamp(value: str) -> pd.Timestamp:
    """Interpret ISO dates in UTC; convert explicit offsets to UTC."""
    try:
        normalized = value.strip().replace("Z", "+00:00")
        # Python 3.10 requires a dot and exactly 3 or 6 fractional digits.
        normalized = re.sub(
            r"(\d{2}:\d{2}:\d{2})[.,](\d{1,6})(?!\d)",
            lambda match: match[1] + "." + match[2].ljust(6, "0"),
            normalized,
        )
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        stamp = pd.Timestamp(parsed.astimezone(timezone.utc))
        # Verify that pandas can represent the value in our common frame dtype.
        _ = stamp.value
        return stamp
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"Invalid ISO timestamp: {value!r}") from exc


def _record(timestamp: str, level: str, message: str, line: int) -> dict:
    level = level.strip().upper()
    level = LEVEL_ALIASES.get(level, level)
    if level not in LEVELS:
        raise ValueError(f"Unknown log level: {level!r}")
    if not message.strip():
        raise ValueError("Empty message")
    return {
        "timestamp": parse_timestamp(timestamp),
        "level": level,
        "message": message.strip(),
        "source_line": line,
    }


def read_logs(path: str | Path) -> ParseResult:
    """Read UTF-8 .log or .csv; blank lines are ignored, invalid rows reported."""
    path = Path(path)
    if path.suffix.lower() not in {".log", ".csv"}:
        raise ValueError("Input must be a .log or .csv file")

    records: list[dict] = []
    issues: list[ParseIssue] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        if path.suffix.lower() == ".csv":
            reader = csv.DictReader(handle, strict=True)
            required = {"timestamp", "level", "message"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError("CSV requires headers: timestamp,level,message")
            if len(reader.fieldnames) != len(set(reader.fieldnames)):
                raise ValueError("CSV contains duplicate headers")
            try:
                for row in reader:
                    try:
                        if None in row or any(row[key] is None for key in required):
                            raise ValueError("CSV row does not match its header")
                        records.append(_record(
                            row["timestamp"], row["level"], row["message"], reader.line_num
                        ))
                    except ValueError as exc:
                        issues.append(ParseIssue(reader.line_num, str(exc)))
            except csv.Error as exc:
                # Broken quoting makes subsequent record boundaries unreliable.
                raise ValueError(f"Malformed CSV near line {reader.line_num}: {exc}") from exc
        else:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                match = LOG_PATTERN.fullmatch(line.strip())
                if not match:
                    issues.append(ParseIssue(line_number, "Expected: ISO timestamp LEVEL message"))
                    continue
                try:
                    records.append(_record(
                        match["timestamp"], match["level"] or match["bracket_level"],
                        match["message"], line_number,
                    ))
                except ValueError as exc:
                    issues.append(ParseIssue(line_number, str(exc)))

    events = pd.DataFrame(records, columns=["timestamp", "level", "message", "source_line"])
    events["timestamp"] = pd.to_datetime(events["timestamp"], utc=True)
    events = events.sort_values("timestamp", kind="stable").reset_index(drop=True)
    return ParseResult(events, issues)
