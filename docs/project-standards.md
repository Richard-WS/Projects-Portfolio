# Project standards

Every project in this portfolio follows the same rules, so anyone — a recruiter, a hiring manager, or future-me — can drop into any folder and know exactly where things are.

## The rules

1. **One project = one folder**, under `data/`, `ai-ml/`, or `it-ops/`, with a kebab-case name (`data/energy-demand-forecast`).
2. **Every new project follows the same layout** — the structure below (package code in `src/`, tests in `tests/`, raw data gitignored) is what the finished projects in this repo demonstrate. Copy an existing project folder as a starting point and rename it.
3. **Python projects** use `pyproject.toml`, a `src/` package layout, and `pytest`.
4. **No secrets.** Real credentials live in `.env` (gitignored); the committed `.env.example` shows only the shape.
5. **No raw data in git.** `data/raw/` is gitignored. Small, licence-clean samples may be committed under `data/samples/` with provenance notes in the project README.
6. **Every project has a README**: problem → approach → results → how to run it.
7. **CI must pass.** `pytest` runs for every project on every push (see `.github/workflows/ci.yml`).

## What a finished project looks like

```
data/my-project/
├── README.md            # problem, approach, results, quick start
├── pyproject.toml       # metadata + deps + pytest config
├── .env.example         # environment shape only, never values
├── src/my_project/      # package code
├── tests/               # pytest suite
├── notebooks/           # exploration / analysis (data & ai-ml projects)
└── data/
    ├── raw/             # gitignored — generated or downloaded on setup
    └── samples/         # optional: small committed samples for demos
```
