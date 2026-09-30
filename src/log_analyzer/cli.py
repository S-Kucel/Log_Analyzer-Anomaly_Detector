"""Command-line entry point and application orchestration."""

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from log_analyzer.analysis import filter_events, summarize
from log_analyzer.anomalies import DetectorConfig, detect_anomalies
from log_analyzer.parser import LEVELS, read_logs
from log_analyzer.reporting import export_paths, plot_activity, print_report, write_report


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Expected a positive integer")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze logs and detect unusual activity using transparent rules.")
    parser.add_argument("input", type=Path, help="UTF-8 .log or .csv file")
    parser.add_argument("--since", help="Inclusive ISO timestamp or date (UTC by default)")
    parser.add_argument("--until", help="Inclusive ISO timestamp, or an entire date")
    parser.add_argument("--level", action="append", type=str.upper, choices=LEVELS, help="Include a level; may be repeated")
    parser.add_argument("--contains", help="Case-insensitive literal text filter")
    parser.add_argument("--top", type=_positive_int, default=5, help="Number of most common messages (default: 5)")
    parser.add_argument("--window-minutes", type=_positive_int, default=5, help="Anomaly/plot window size (default: 5)")
    parser.add_argument("--login-threshold", type=_positive_int, default=10, help="Failed login messages per window (default: 10)")
    parser.add_argument("--output", type=Path, help="JSON report or CSV events plus summary/anomaly CSV files")
    parser.add_argument("--plot", type=Path, help="Save event/error chart as .png")
    parser.add_argument("--strict", action="store_true", help="Fail if any record is invalid")
    return parser


def _validate_outputs(input_path: Path, output: Path | None, plot: Path | None) -> None:
    paths = export_paths(output) if output else []
    if plot:
        if plot.suffix.lower() != ".png":
            raise ValueError("Plot output must end in .png")
        paths.append(plot)
    resolved = [path.resolve() for path in paths]
    if input_path.resolve() in resolved:
        raise ValueError("An output path would overwrite the input file")
    if len(resolved) != len(set(resolved)):
        raise ValueError("Output paths must be distinct")
    if any(path.exists() and path.samefile(input_path) for path in paths):
        raise ValueError("An output path points to the input file")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        _validate_outputs(args.input, args.output, args.plot)
        parsed = read_logs(args.input)
        if parsed.issues:
            print(f"Warning: rejected {len(parsed.issues)} invalid record(s).", file=sys.stderr)
            for issue in parsed.issues[:5]:
                print(f"  Line {issue.line}: {issue.reason}", file=sys.stderr)
            if len(parsed.issues) > 5:
                print("  Remaining issues are included in the JSON report.", file=sys.stderr)
            if args.strict:
                raise ValueError("Strict mode: input contains invalid records")
        if parsed.events.empty and parsed.issues:
            raise ValueError("Input contains no valid log records")
        events = filter_events(parsed.events, args.since, args.until, args.level, args.contains)
        config = DetectorConfig(window_minutes=args.window_minutes, login_threshold=args.login_threshold)
        report = {
            "schema_version": 1,
            "input": {
                "file": str(args.input),
                "parsed_events": len(parsed.events),
                "rejected_records": len(parsed.issues),
                "issues": [asdict(issue) for issue in parsed.issues],
            },
            "filters": {"since": args.since, "until": args.until, "levels": args.level, "contains": args.contains},
            "detector": asdict(config),
            "summary": summarize(events, args.top),
            "anomalies": detect_anomalies(events, config),
        }
        print_report(report)
        if events.empty:
            print("\nNo events to analyze for this input and these filters.")
        if args.output:
            for path in write_report(report, events, args.output):
                print(f"Saved: {path}")
        if args.plot:
            plot_activity(events, args.plot, args.window_minutes)
            print(f"Saved: {args.plot}")
        return 0
    except (OSError, ValueError, OverflowError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
