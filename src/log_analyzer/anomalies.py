"""Explainable alerts using thresholds and historical time windows."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from log_analyzer.analysis import event_counts

FAILED_LOGIN_PATTERN = (
    r"failed\s+(?:login|logon|password|authentication)\b|"
    r"(?:login|logon|authentication)\s+failed\b|invalid\s+credentials\b"
)


@dataclass(frozen=True)
class DetectorConfig:
    window_minutes: int = 5
    baseline_windows: int = 12
    min_history: int = 3
    login_threshold: int = 10
    min_errors: int = 10
    min_events: int = 50
    spike_factor: float = 3.0
    sigma: float = 3.0

    def __post_init__(self) -> None:
        for name in ("window_minutes", "baseline_windows", "min_history", "login_threshold", "min_errors", "min_events"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.min_history > self.baseline_windows:
            raise ValueError("min_history cannot exceed baseline_windows")
        if not np.isfinite(self.spike_factor) or self.spike_factor <= 1:
            raise ValueError("spike_factor must be finite and greater than 1")
        if not np.isfinite(self.sigma) or self.sigma <= 0:
            raise ValueError("sigma must be finite and positive")


def detect_anomalies(events: pd.DataFrame, config: DetectorConfig | None = None) -> list[dict]:
    config = config or DetectorConfig()
    counts = event_counts(events, config.window_minutes)
    if counts.empty:
        return []
    indexed = events.set_index("timestamp")
    failed_logins = indexed["message"].str.contains(
        FAILED_LOGIN_PATTERN, case=False, regex=True, na=False
    )
    counts["failed_logins"] = failed_logins.astype(int).resample(
        f"{config.window_minutes}min", origin="epoch"
    ).sum().reindex(counts.index, fill_value=0)
    anomalies: list[dict] = []

    def add_alert(stamp, kind, observed, threshold, reason, baseline_mean=None):
        anomalies.append({
            "type": kind,
            "start": stamp.isoformat(),
            "end": (stamp + pd.Timedelta(minutes=config.window_minutes)).isoformat(),
            "count": int(observed),
            "threshold": float(threshold),
            "baseline_mean": baseline_mean,
            "reason": reason,
        })

    for index, (stamp, row) in enumerate(counts.iterrows()):
        if row["failed_logins"] >= config.login_threshold:
            add_alert(stamp, "failed_logins", row["failed_logins"], config.login_threshold,
                      f"At least {config.login_threshold} failed login messages in one window")
        history = counts.iloc[max(0, index - config.baseline_windows):index]
        if len(history) < config.min_history:
            continue
        for column, kind, minimum in (
            ("errors", "error_spike", config.min_errors),
            ("events", "activity_spike", config.min_events),
        ):
            values = history[column].to_numpy(dtype=float)
            mean = float(np.mean(values))
            std = float(np.std(values))
            threshold = max(minimum, config.spike_factor * mean, mean + config.sigma * std)
            if row[column] >= threshold:
                add_alert(
                    stamp, kind, row[column], threshold,
                    f"{column} >= max({minimum}, {config.spike_factor:g} * previous mean, "
                    f"previous mean + {config.sigma:g} * previous std); "
                    f"based on {len(history)} preceding windows",
                    baseline_mean=mean,
                )
    return anomalies
