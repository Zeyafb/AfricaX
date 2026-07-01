"""Make the project importable and give each test an isolated CSV."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data_store as ds  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Point data_store at a throwaway CSV so tests never touch real data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(ds, "DATA_DIR", data_dir)
    monkeypatch.setattr(ds, "CSV_PATH", data_dir / "restaurants.csv")
    return ds
