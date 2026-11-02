---
description: "Log Analyzer / Anomaly Detector project assistant"
model: GPT-4.1
tools:
  - codebase
  - editFiles
  - search
  - runCommands
  - terminalLastCommand
---

# Log Analyzer / Anomaly Detector

You are working in a Python CLI project that parses log files, computes summary statistics, and detects suspicious activity using explainable heuristics.

## Repository goals
- Keep the analyzer accurate and deterministic.
- Respect the project structure under `src/log_analyzer/`.
- Prefer minimal, maintainable edits.
- Validate changes with the project test suite.

## Project commands
```powershell
python -m pytest -q
python -m log_analyzer examples\server.log --output reports\analysis.json --plot reports\activity.png
```

## Rules
- Follow the architecture in `README.md` and `AGENTS.md`.
- Use `pytest` for verification, not ad hoc assertions alone.
- When editing parser or anomaly logic, add or update regression tests.
- Keep CLI behavior and output formatting consistent.
- Avoid introducing new third-party dependencies unless clearly required.

## File map
- `src/log_analyzer/parser.py` for input parsing and malformed-record handling
- `src/log_analyzer/analysis.py` for filtering and statistical summaries
- `src/log_analyzer/anomalies.py` for threshold logic and anomaly detection
- `src/log_analyzer/reporting.py` for JSON/CSV/PNG outputs and terminal reports
- `src/log_analyzer/cli.py` for entry points and argument validation
- `tests/` for verification coverage

## Working style
- Make focused edits and keep changes easy to review.
- Explain the root cause before changing code when debugging bugs.
- If a change affects user-visible CLI output, ensure the README or tests reflect the behavior.
