from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def example_dir():
    return Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture
def make_events():
    def create(rows):
        frame = pd.DataFrame(rows, columns=["timestamp", "level", "message"])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
        frame["source_line"] = range(1, len(frame) + 1)
        return frame.sort_values("timestamp").reset_index(drop=True)
    return create
