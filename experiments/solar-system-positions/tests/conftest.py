"""Shared fixtures: tiny deterministic position tables for build tests."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FIXTURE_CSV = """date,planet,x_au,y_au
2000-01-01,earth,0.9830,0.0000
2000-01-01,mars,1.4000,0.1000
2000-02-01,earth,0.9900,0.0500
2000-02-01,mars,1.3800,0.2000
"""


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def fixture_csv(tmp_path: Path) -> Path:
    p = tmp_path / "fixture.csv"
    p.write_text(FIXTURE_CSV)
    return p


@pytest.fixture
def fixture_template(tmp_path: Path) -> Path:
    p = tmp_path / "viewer_template.html"
    p.write_text("<html><script>const DATA = __POSITIONS_JSON__;</script></html>")
    return p
