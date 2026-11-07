"""Shared pytest fixtures: a temp drawer, synthetic items, quiet setup.

All fixture data is synthetic - no personal data, ever.
"""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from junk_drawer.store import Drawer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_path() -> Path:
    return FIXTURES


@pytest.fixture
def sample_drawer(tmp_path: Path) -> Drawer:
    """A copy of the sample drawer, so tests never mutate the fixture file."""
    path = tmp_path / "sample_drawer.json"
    shutil.copy(FIXTURES / "sample_drawer.json", path)
    return Drawer(path)


@pytest.fixture
def empty_drawer(tmp_path: Path) -> Drawer:
    return Drawer(tmp_path / "empty.json")


@pytest.fixture
def fresh_drawer(tmp_path: Path) -> Drawer:
    return Drawer(tmp_path / "drawer.json")
