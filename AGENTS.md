# AGENTS.md

## Project purpose
This repository contains a Python CLI tool for parsing log files, computing summary statistics, and flagging anomalous patterns in event streams.

## Working conventions
- Keep production code under `src/log_analyzer/`.
- Prefer small, well-named functions with clear separation between parsing, analysis, anomaly detection, and reporting.
- Preserve the existing CLI contract: the package is exposed via `log-analyzer` and as `python -m log_analyzer`.
- Treat input validation and error reporting as first-class behavior.
- Do not change the public behavior of detection rules without updating tests and documentation.

## Validation
Run the project test suite before finalizing significant changes:

```powershell
python -m pytest -q
```

For targeted checks, prefer the smallest relevant pytest invocation.

## Common commands
```powershell
python -m pip install -r requirements.txt
python -m log_analyzer examples\server.log --output reports\analysis.json --plot reports\activity.png
```

## Code architecture
- `src/log_analyzer/parser.py`: parse log/CSV input and collect malformed records
- `src/log_analyzer/analysis.py`: filtering, aggregation, and summary statistics
- `src/log_analyzer/anomalies.py`: anomaly rules and thresholds
- `src/log_analyzer/reporting.py`: terminal output, JSON/CSV exports, and plots
- `src/log_analyzer/cli.py`: CLI wiring and argument handling
- `tests/`: pytest coverage for parser, analysis, anomaly detection, and CLI behavior

## Expectations for edits
- Prefer minimal, targeted changes.
- Add or update tests when changing behavior.
- Keep output deterministic and avoid unnecessary dependencies.
- If a bug fix touches parsing or filtering logic, verify both CLI effects and regression tests.
