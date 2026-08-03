# Lemonade Wars — a beverage-empire business simulation

A single-player business simulation that blends the recipe economics of
*Lemonade Stand* with the travelling commodity markets of *Drug Wars*: you
run a lemonade cart that grows into a beverage empire across five city
districts. Every decision is a business decision — sourcing, pricing,
production, logistics, staffing, finance, marketing, and risk.

**Play it in your browser:** https://richard-ws.github.io/Projects-Portfolio/experiments/lemonade-wars/web/
(runs on phones and laptops — the UI adapts to portrait and landscape)

## Problem

Classic business-simulation games each nailed one half of the fun. *Lemonade
Stand* made recipe economics tense: cost of goods, batch sizing, spoilage,
weather. *Drug Wars* made markets alive: commodity prices that swing by
location, arbitrage, travel risk, and the nerve to buy low and sell high.
Nothing in between gave you both — a full business where the *product* is
something you design, and the *market* is something you move between.

## Approach

The whole game is a pure-Python simulation core with a thin Pygame UI:

1. **Simulation core (`src/lemonwars/`, zero pygame imports).** A day-cycle
   engine with deterministic seeded RNG, so every campaign is reproducible
   and the whole game runs headless in CI.
   - **Market** — five districts, each with its own ingredient prices that
     drift daily and react to supply shocks; price arbitrage pays for
     travelling between districts (the *Drug Wars* half).
   - **Recipe designer** — pick ingredients, sweetness, ice level and
     temperature per product; every choice shifts a flavour vector that
     drives district-level demand (the *Lemonade Stand* half).
   - **Customers** — demand is the product of district demographics, weather,
     season, reputation, advertising awareness, competition, tier capacity
     and technology; sales resolve per-customer with price sensitivity and
     satisfaction (repeat customers).
   - **Business layer** — loans with credit scoring, weekly taxes and
     payroll, insurance against business and crime events, staff hiring with
     morale, equipment and technology unlocks, five business tiers from cart
     to restaurant.
   - **Autoplay** — a scripted greedy player that plays complete campaigns,
     which is also what the smoke tests run headlessly.
2. **Responsive UI (`src/lemonwars/ui/`).** Renders to a fixed logical grid
   (1280×800 landscape / 720×1280 portrait, chosen from the window aspect)
   then aspect-fits it onto the real window — one layout codebase that
   adapts to laptops and phones. Touch is just click: pygbag maps taps to
   mouse events.
3. **Dual delivery.** `python main.py` runs the desktop version; a committed
   pygbag build under `web/` runs in any browser from GitHub Pages.
   Rebuild with `./build_web.sh`.

## Results

- **61 tests green** (run in CI on a bare runner — no display needed):
  market drift and arbitrage, recipe cost/quality, demand and sales
  resolution, day-cycle finance (taxes, interest, insurance, spoilage),
  save/load round-trips, full-campaign autoplay, and a headless UI smoke
  run that clicks through every screen and renders every tab in both
  orientations.
- The autoplay economy is stable: the scripted player survives 120-day
  campaigns and grows net worth on Normal; bankruptcy (debt ceiling, cash
  floor, or three health-code failures) is a real end state, not a formality.
- Deterministic seeds make every run reproducible — a campaign on seed *N*
  is the same campaign on every platform.

## How to run

**Browser (no install):** open the web build link above.

**Desktop:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

**Tests:**

```bash
pip install -e ".[dev]"
python -m pytest
```

**Rebuild the web version:**

```bash
pip install pygbag
./build_web.sh
```

## Project layout

```
lemonade-wars/
├── main.py                  # desktop entry point (also the pygbag target)
├── build_web.sh             # rebuild + stage the web version
├── web/                     # committed pygbag build, served by GitHub Pages
├── src/lemonwars/
│   ├── data.py              # static data: ingredients, districts, weather, …
│   ├── market.py            # per-district ingredient markets
│   ├── world.py             # weather & seasons
│   ├── recipes.py           # recipe designer: usage, flavour, cost, quality
│   ├── customers.py         # demand model + daily sales resolution
│   ├── player.py            # player state, staff, spoilage
│   ├── events.py            # random events + achievements
│   ├── sim.py               # GameState: day cycle, actions, finance, endgame
│   ├── saveload.py          # JSON save/load
│   ├── autoplay.py          # scripted player for tests & demo
│   └── ui/                  # responsive Pygame UI (theme, widgets, screens)
└── tests/                   # 61 tests across 7 suites
```
