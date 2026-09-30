"""Generate reproducible synthetic logs, with three deliberately unusual windows."""

import csv
from datetime import datetime, timedelta
from pathlib import Path


def main() -> None:
    target = Path(__file__).resolve().parents[1] / "examples"
    target.mkdir(exist_ok=True)
    start = datetime(2026, 9, 30, 12, 0)
    events: list[tuple[datetime, str, str]] = []
    for minute in range(120):
        stamp = start + timedelta(minutes=minute)
        events.append((stamp, "INFO", "Request completed"))
        events.append((stamp + timedelta(seconds=10), "INFO", "Health check OK"))
        if minute % 10 == 0:
            events.append((stamp + timedelta(seconds=20), "WARNING", "Response time above 500 ms"))
        if minute % 15 == 0:
            events.append((stamp + timedelta(seconds=30), "ERROR", "Database timeout"))

    for second in range(25):
        events.append((start + timedelta(minutes=30, seconds=second), "WARNING", "Failed login for user demo"))
    for second in range(40):
        events.append((start + timedelta(minutes=60, seconds=second), "ERROR", "Database timeout"))
    for second in range(100):
        events.append((start + timedelta(minutes=90, seconds=second), "INFO", "Search request completed"))
    events.sort(key=lambda event: event[0])

    with (target / "server.log").open("w", encoding="utf-8", newline="\n") as handle:
        for stamp, level, message in events:
            handle.write(f"{stamp.isoformat(sep=' ')} {level} {message}\n")
    with (target / "server.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "level", "message"])
        writer.writerows((stamp.isoformat(), level, message) for stamp, level, message in events)
    print(f"Generated {len(events)} events in {target}")


if __name__ == "__main__":
    main()
