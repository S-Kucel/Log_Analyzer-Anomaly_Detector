"""Console-friendly reports, machine-readable exports and PNG plots."""

import csv
import json
from pathlib import Path

import pandas as pd

from log_analyzer.analysis import event_counts

ANOMALY_COLUMNS = ["type", "start", "end", "count", "threshold", "baseline_mean", "reason"]


def export_paths(path: Path) -> list[Path]:
    if path.suffix.lower() == ".json":
        return [path]
    if path.suffix.lower() == ".csv":
        return [path, path.with_name(f"{path.stem}.summary.csv"), path.with_name(f"{path.stem}.anomalies.csv")]
    raise ValueError("Report output must end in .json or .csv")


def write_report(report: dict, events: pd.DataFrame, path: Path) -> list[Path]:
    paths = export_paths(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    else:
        events.to_csv(path, index=False, encoding="utf-8")
        summary = report["summary"]
        metrics = {
            "total_events": summary["total_events"],
            "parsed_events": report["input"]["parsed_events"],
            "rejected_records": report["input"]["rejected_records"],
            "anomalies": len(report["anomalies"]),
            **summary["levels"],
            "start": summary["time_range"]["start"],
            "end": summary["time_range"]["end"],
        }
        with paths[1].open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            writer.writerows(metrics.items())
        pd.DataFrame(report["anomalies"], columns=ANOMALY_COLUMNS).to_csv(paths[2], index=False, encoding="utf-8")
    return paths


def plot_activity(events: pd.DataFrame, path: Path, window_minutes: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    counts = event_counts(events, window_minutes)
    fig, axes = plt.subplots(2, 1, figsize=(11, 6), sharex=True, layout="constrained")
    try:
        fig.suptitle("Log activity", fontsize=17)
        for axis, column, label, color in (
            (axes[0], "events", "All events", "#2563eb"),
            (axes[1], "errors", "ERROR + CRITICAL", "#dc2626"),
        ):
            if not counts.empty:
                axis.bar(counts.index, counts[column], width=window_minutes / 1440 * 0.85,
                         align="edge", color=color)
            else:
                axis.text(0.5, 0.5, "No events match the filters", ha="center", transform=axis.transAxes)
            axis.set_ylabel(label)
            axis.set_ylim(bottom=0)
            axis.grid(axis="y", alpha=0.2)
            axis.set_axisbelow(True)
        locator = mdates.AutoDateLocator()
        axes[1].xaxis.set_major_locator(locator)
        axes[1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz="UTC"))
        axes[1].set_xlabel(f"Time (UTC), {window_minutes}-minute windows")
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=160)
    finally:
        plt.close(fig)


def print_report(report: dict) -> None:
    summary = report["summary"]
    print(f"Total events: {summary['total_events']:,}")
    print(f"Parsed: {report['input']['parsed_events']:,} | Rejected: {report['input']['rejected_records']:,}")
    for level, count in summary["levels"].items():
        print(f"{level}: {count:,}")
    if summary["time_range"]["start"]:
        print(f"Range (UTC): {summary['time_range']['start']} to {summary['time_range']['end']}")
    for heading, key in (("Most common messages", "most_common_messages"), ("Most common errors", "most_common_errors")):
        print(f"\n{heading}:")
        for item in summary[key]:
            print(f"  {item['count']:>5}  {item['message']}")
        if not summary[key]:
            print("  None")
    print("\nEvents per hour (UTC):")
    for hour in summary["hourly_counts"]:
        print(f"  {hour['start']}: {hour['events']} events, {hour['errors']} errors")
    print(f"\nDetected anomalies: {len(report['anomalies'])}")
    for anomaly in report["anomalies"]:
        print(f"  {anomaly['start']} to {anomaly['end']} [end exclusive]")
        print(f"    {anomaly['type']}: {anomaly['count']} (threshold {anomaly['threshold']:.2f})")
        print(f"    {anomaly['reason']}")
