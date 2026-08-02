"""Viewer build: CSV -> JSON grouping, template rendering, output integrity."""

from __future__ import annotations

import json

import pytest

from solarpositions.build import csv_to_json, render_html


def test_csv_to_json_groups_by_planet(fixture_csv):
    data = csv_to_json(fixture_csv, precision=6)
    assert data["dates"] == ["2000-01-01", "2000-02-01"]
    assert set(data["planets"]) == {"earth", "mars"}
    assert data["planets"]["earth"] == [[0.983, 0.0], [0.99, 0.05]]


def test_csv_to_json_detects_mismatch(fixture_csv):
    import csv as _csv
    from pathlib import Path

    bad = Path(fixture_csv)
    lines = bad.read_text().splitlines()
    # drop one mars row -> mars has 1 entry, earth 2
    bad.write_text("\n".join(lines[:2] + lines[4:]) + "\n")
    with pytest.raises(ValueError, match="has 1 rows but 2 dates"):
        csv_to_json(bad)


def test_render_html_embeds_data(fixture_csv, fixture_template, tmp_path):
    data = csv_to_json(fixture_csv, precision=6)
    out = tmp_path / "viewer.html"
    render_html(fixture_template, data, out, precision=6)

    html = out.read_text()
    assert "__POSITIONS_JSON__" not in html
    # the embedded JSON should be parseable by pulling it out of the script tag
    start = html.index("const DATA = ") + len("const DATA = ")
    end = html.index(";", start)
    payload = json.loads(html[start:end])
    assert payload["dates"] == ["2000-01-01", "2000-02-01"]
    assert payload["planets"]["mars"] == [[1.4, 0.1], [1.38, 0.2]]
    assert payload["colors"]["earth"].startswith("#")


def test_render_html_rejects_template_without_placeholder(fixture_csv, tmp_path):
    tpl = tmp_path / "t.html"
    tpl.write_text("<html>no placeholder here</html>")
    data = csv_to_json(fixture_csv, precision=6)
    with pytest.raises(ValueError, match="__POSITIONS_JSON__"):
        render_html(tpl, data, tmp_path / "out.html")
