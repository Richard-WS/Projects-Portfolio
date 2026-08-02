"""Build the self-contained HTML viewer from the positions CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

PLANET_COLORS = {
    "mercury": "#b8b8b8",
    "venus": "#e8c87a",
    "earth": "#4da6ff",
    "mars": "#e07050",
    "jupiter": "#d8a06a",
    "saturn": "#e6cf8f",
    "uranus": "#7fd4d4",
    "neptune": "#5a7df0",
    "pluto": "#a0917a",
}

_PLACEHOLDER = "__POSITIONS_JSON__"


def csv_to_json(csv_path: str | Path, precision: int = 6) -> dict:
    """Group the CSV into {dates: [...], planets: {name: [[x, y], ...]}}."""
    dates: list[str] = []
    planets: dict[str, list[list[float]]] = {}
    with open(csv_path, newline="") as fh:
        for row in csv.DictReader(fh):
            if row["date"] not in dates:
                dates.append(row["date"])
            planets.setdefault(row["planet"], []).append(
                [
                    round(float(row["x_au"]), precision),
                    round(float(row["y_au"]), precision),
                ]
            )
    for name, coords in planets.items():
        if len(coords) != len(dates):
            raise ValueError(
                f"planet {name!r} has {len(coords)} rows but {len(dates)} dates"
            )
    return {"dates": dates, "planets": planets, "colors": PLANET_COLORS}


def render_html(
    template_path: str | Path,
    data: dict,
    out_path: str | Path,
    precision: int = 6,
) -> None:
    """Render the viewer template with the positions JSON embedded."""
    template = Path(template_path).read_text()
    payload = {
        "dates": data["dates"],
        "planets": data["planets"],
        "colors": data["colors"],
    }
    encoded = json.dumps(payload, separators=(",", ":"))
    if _PLACEHOLDER not in template:
        raise ValueError(f"template {template_path} is missing {_PLACEHOLDER}")
    html = template.replace(_PLACEHOLDER, encoded)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
