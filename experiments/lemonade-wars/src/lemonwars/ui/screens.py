"""Screens: title, difficulty, the main tabbed game screen, night report and
end-of-campaign. All layout is in 1280x800 design units and adapts to
landscape (laptop) and portrait (phone) via theme.S() and orientation checks.
"""

from __future__ import annotations

import math

import pygame

from . import theme
from .theme import (S, bar, fmt, font, money, rect, text, wrap_text)
from .widgets import Button, ScrollArea, Slider, TabBar, Toggle, scroll_draw

from .. import data
from ..customers import reference_price
from ..recipes import Recipe, TEMPS
from ..events import ACHIEVEMENTS

TABS = ["Market", "Recipe", "Sell", "Districts", "Staff", "Finance", "News"]


# ==========================================================================
# Shared helpers
# ==========================================================================

def _season_weather(game):
    d = game.player.district
    wkey = game.world.weather.get(d, "sunny")
    w = data.WEATHER[wkey]
    season = data.season_for_day(game.day)
    return w, season


def _status_color(v: float) -> tuple:
    if v >= 0.66:
        return theme.GREEN
    if v >= 0.33:
        return theme.ORANGE
    return theme.RED


# ==========================================================================
# Title screen
# ==========================================================================

class TitleScreen:
    def __init__(self, app):
        self.app = app
        self.can_continue = False

    def handle(self, ev) -> bool:
        if ev.type != pygame.MOUSEBUTTONUP or ev.button != 1:
            return False
        for b in self._buttons():
            if b.hit(ev.pos):
                if b.label == "New Campaign":
                    self.app.mode = "difficulty"
                elif b.label == "Continue":
                    g = self.app.load_autosave()
                    if g:
                        self.app.game = g
                        self.app.mode = "game"
                        self.app.notice(f"Welcome back — day {g.day}.")
                elif b.label == "Autoplay Demo":
                    self.app.start_game("normal", autoplay=True)
                return True
        return False

    def _buttons(self):
        w, h = self.app.size
        s = theme.scale(w, h)
        cx = w / 2
        bw, bh = int(260 * s), int(54 * s)
        ys = [int(h * 0.52), int(h * 0.52) + int(70 * s), int(h * 0.52) + int(140 * s)]
        out = []
        labels = ["New Campaign", "Continue", "Autoplay Demo"]
        for i, (label, y) in enumerate(zip(labels, ys)):
            b = Button(cx - bw / 2, y, bw, bh, label, accent=(i == 0), size=22)
            if label == "Continue" and not self.can_continue:
                b.enabled = False
            out.append(b)
        return out

    def draw(self, surf):
        w, h = self.app.size
        surf.fill(theme.BG)
        s = theme.scale(w, h)
        cx = w / 2
        text(surf, "LEMONADE WARS", int(64 * s), theme.ACCENT, (cx, int(h * 0.26)),
             center=True, bold=True)
        text(surf, "A beverage-empire business simulation", int(20 * s),
             theme.MUTED, (cx, int(h * 0.34)), center=True)
        text(surf, "Recipe economics x travelling commodity markets", int(16 * s),
             theme.FAINT, (cx, int(h * 0.395)), center=True)
        for b in self._buttons():
            b.draw(surf)
        text(surf, "Buy low · Produce · Travel · Sell high · Build an empire",
             int(15 * s), theme.FAINT, (cx, int(h * 0.86)), center=True)


# ==========================================================================
# Difficulty screen
# ==========================================================================

class DifficultyScreen:
    def __init__(self, app):
        self.app = app

    def handle(self, ev) -> bool:
        if ev.type != pygame.MOUSEBUTTONUP or ev.button != 1:
            return False
        for b in self._cards():
            if b.hit(ev.pos):
                key = b.label.split(" — ")[0].lower().replace(" ", "_")
                self.app.start_game(key)
                return True
        for b in self._back():
            if b.hit(ev.pos):
                self.app.mode = "title"
                return True
        return False

    def _cards(self):
        w, h = self.app.size
        s = theme.scale(w, h)
        n = len(data.DIFFICULTIES)
        gap = int(14 * s)
        cw = int(300 * s)
        ch = int(240 * s)
        total = n * cw + (n - 1) * gap
        x0 = int((w - total) / 2)
        y0 = int(h * 0.40)
        out = []
        for i, (key, d) in enumerate(data.DIFFICULTIES.items()):
            label = f"{d.name} — {d.desc}"
            b = Button(x0 + i * (cw + gap), y0, cw, ch, label, accent=(key == "normal"), size=17)
            b._key = key
            b._d = d
            out.append(b)
        return out

    def _back(self):
        return [Button(24, 24, 120, 40, "< Back", muted=True)]

    def draw(self, surf):
        w, h = self.app.size
        surf.fill(theme.BG)
        s = theme.scale(w, h)
        text(surf, "Choose Difficulty", int(34 * s), theme.TEXT, (w / 2, int(h * 0.16)),
             center=True, bold=True)
        for b in self._cards():
            b.draw(surf)
            d = b._d
            cx, cy = b.rect().center
            r = b.rect()
            days = f"{d.days} days" if d.days else "Endless"
            lines = [
                f"{days} · loans ×{d.loan_mult:.2f}",
                f"events ×{d.event_mult:.2f} · weather ×{d.weather_mult:.2f}",
                f"competitors ×{d.competitor_mult:.2f}",
            ]
            for i, ln in enumerate(lines):
                text(surf, ln, 14, theme.MUTED, (r.centerx, r.bottom - S(58) + i * S(20)),
                     center=True)
        for b in self._back():
            b.draw(surf)
        text(surf, "Simulation: endless mode with no campaign clock.",
             int(14 * s), theme.FAINT, (w / 2, int(h * 0.88)), center=True)


# ==========================================================================
# Game screen
# ==========================================================================

class GameScreen:
    def __init__(self, app):
        self.app = app
        self.tab = 0
        self.qty: dict[str, int] = {}
        self.batch = 60
        self.price_frac = 0.5
        self.scrolls: dict[int, ScrollArea] = {}
        self.panel_widgets: list = []
        self.last_layout = None
        self._selected_product = None

    # -------------------------------------------------------------- layout

    def _header_rect(self):
        w, h = self.app.size
        if h > w:
            return (0, 0, w, int(96 * theme.scale(w, h)))
        return (0, 0, w, int(72 * theme.scale(w, h)))

    def _tabs_rect(self):
        w, h = self.app.size
        s = theme.scale(w, h)
        hr = self._header_rect()
        if h > w:
            return (0, hr[3], w, int(64 * s))
        return (0, hr[3], w, int(52 * s))

    def _content_rect(self):
        w, h = self.app.size
        hr = self._header_rect()
        tr = self._tabs_rect()
        pad = S(14)
        return (pad, hr[3] + tr[3] + pad, w - 2 * pad, h - hr[3] - tr[3] - 2 * pad)

    # ------------------------------------------------------------- events

    def handle(self, ev) -> bool:
        header = self._header_widgets()
        tabs = self._tab_widgets()
        for b in header:
            if b.handle(ev, ev.pos):
                return True
        if tabs.handle(ev, ev.pos):
            return True
        self._ensure_panel()
        for b in self.panel_widgets:
            if b.handle(ev, ev.pos):
                return True
        return False

    # --------------------------------------------------------------- draw

    def draw(self, surf):
        self._draw_header(surf)
        self._tab_widgets().draw(surf)
        self._ensure_panel()
        self._draw_panel(surf)

    # ----------------------------------------------------------- header

    def _header_widgets(self):
        w, h = self.app.size
        hr = self._header_rect()
        portrait = h > w
        s = theme.scale(w, h)
        out = []
        if portrait:
            end = Button(w - S(96) - 8, hr[3] // 2 - S(26), 96, 52, "End Day",
                         accent=True, cb=self._end_day)
            end.enabled = self.app.game.phase == "planning" and not self.app.game.game_over
            out.append(end)
            aut = Toggle(8, hr[3] // 2 - S(18), 150, 40, "Autoplay",
                         value=self.app.autoplay_on, cb=self._toggle_auto)
            out.append(aut)
        else:
            aut = Toggle(S(18), S(18), 140, 40, "Autoplay",
                         value=self.app.autoplay_on, cb=self._toggle_auto)
            out.append(aut)
            end = Button(w - S(130) - 16, S(16), 130, 40, "End Day",
                         accent=True, cb=self._end_day)
            end.enabled = self.app.game.phase == "planning" and not self.app.game.game_over
            out.append(end)
        return out

    def _toggle_auto(self, v):
        self.app.autoplay_on = v

    def _end_day(self):
        app = self.app
        if app.game.phase == "planning" and not app.game.game_over:
            app.game.end_day()
            app.mode = "report"

    def _draw_header(self, surf):
        w, h = self.app.size
        hr = self._header_rect()
        portrait = h > w
        s = theme.scale(w, h)
        rect(surf, theme.PANEL, hr)
        g = self.app.game
        w_profile, season = _season_weather(g)
        p = g.player

        if portrait:
            text(surf, f"Day {g.day}", 15, theme.ACCENT, (S(12), S(8)), bold=True)
            text(surf, f"{season.name} · {w_profile.name}", 13, theme.MUTED,
                 (S(12), S(30)))
            text(surf, f"{data.DISTRICTS[p.district].name} · {p.tier().name}",
                 13, theme.MUTED, (S(12), S(52)))
            cx = w / 2
            text(surf, money(p.cash), 20, theme.GREEN, (cx, S(8)), center=True, bold=True)
            text(surf, f"NW {money(g.net_worth())}  Debt {money(p.debt)}  Rep {p.reputation:.0f}",
                 13, theme.MUTED, (cx, S(36)), center=True)
            text(surf, self.app.notice_text, 13, theme.ORANGE, (cx, S(58)), center=True)
        else:
            text(surf, "LEMONADE WARS", 18, theme.ACCENT, (S(18), S(16)), bold=True)
            text(surf, f"Day {g.day} · {season.name} · {w_profile.name}", 14,
                 theme.TEXT, (S(18), S(42)))
            text(surf, f"{data.DISTRICTS[p.district].name} · {p.tier().name}", 13,
                 theme.MUTED, (S(18), S(58)))
            x = S(250)
            text(surf, "Cash", 12, theme.FAINT, (x, S(10)))
            text(surf, money(p.cash), 20, theme.GREEN, (x, S(26)), bold=True)
            x = S(430)
            text(surf, "Debt", 12, theme.FAINT, (x, S(10)))
            text(surf, money(p.debt), 16, theme.RED if p.debt > 0 else theme.MUTED,
                 (x, S(30)))
            x = S(560)
            text(surf, "Net Worth", 12, theme.FAINT, (x, S(10)))
            text(surf, money(g.net_worth()), 16, theme.TEXT, (x, S(30)))
            x = S(720)
            text(surf, "Reputation", 12, theme.FAINT, (x, S(10)))
            text(surf, f"{p.reputation:.0f}/100", 16, theme.ACCENT, (x, S(30)))
            x = S(880)
            text(surf, "Awareness", 12, theme.FAINT, (x, S(10)))
            text(surf, f"{p.awareness:.0f}", 16, theme.BLUE, (x, S(30)))
            if self.app.notice_text:
                text(surf, self.app.notice_text, 13, theme.ORANGE, (S(1000), S(18)))

    # ------------------------------------------------------------ tab bar

    def _tab_widgets(self):
        tr = self._tabs_rect()
        portrait = self.app.size[1] > self.app.size[0]
        return TabBar(tr[0], tr[1], tr[2], tr[3], TABS, active=self.tab,
                      on_change=self._on_tab, vertical=portrait)

    def _on_tab(self, i):
        self.tab = i
        self.app.notice("")

    # ------------------------------------------------------------- panels

    def _ensure_panel(self):
        if self.last_layout == (self.tab, self.app.size, self.app.game.day):
            return
        area = self._content_rect()
        self.panel_widgets = self._build_panel(area)
        self.last_layout = (self.tab, self.app.size, self.app.game.day)

    def _build_panel(self, area):
        if self.tab == 0:
            return self._panel_market(area)
        if self.tab == 1:
            return self._panel_recipe(area)
        if self.tab == 2:
            return self._panel_sell(area)
        if self.tab == 3:
            return self._panel_districts(area)
        if self.tab == 4:
            return self._panel_staff(area)
        if self.tab == 5:
            return self._panel_finance(area)
        return self._panel_news(area)

    def _draw_panel(self, surf):
        area = self._content_rect()
        r = pygame.Rect(*area)
        rect(surf, theme.PANEL, r)
        if self.tab == 0:
            self._draw_market(surf, r)
        elif self.tab == 1:
            self._draw_recipe(surf, r)
        elif self.tab == 2:
            self._draw_sell(surf, r)
        elif self.tab == 3:
            self._draw_districts(surf, r)
        elif self.tab == 4:
            self._draw_staff(surf, r)
        elif self.tab == 5:
            self._draw_finance(surf, r)
        else:
            self._draw_news(surf, r)

    # ---------------- market ----------------

    def _panel_market(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        row_h = S(40)
        col_w = w // 2 - S(8)
        sc = ScrollArea(x, y, col_w, h - S(10))
        self.scrolls[0] = sc
        ings = list(data.INGREDIENTS)
        yy = S(4)
        for k in ings:
            q = self.qty.get(k, 25)
            btn = Button(col_w - S(64), yy + S(6), 30, S(28), "-",
                         cb=lambda kk=k: self._qty(kk, -1))
            btn._ing = k
            out.append(btn)
            btn2 = Button(col_w - S(30), yy + S(6), 30, S(28), "+",
                          cb=lambda kk=k: self._qty(kk, +1))
            btn2._ing = k
            out.append(btn2)
            buy = Button(col_w - S(200), yy, S(130), S(36), "Buy", accent=True,
                         cb=lambda kk=k: self._buy(kk))
            buy._ing = k
            out.append(buy)
            yy += row_h
        sc.content_h = S(4) + len(ings) * row_h
        self._market_scroll = sc
        # district card widgets (right column): travel buttons handled in districts panel
        self._market_scroll2 = None
        return out

    def _qty(self, k, delta):
        self.qty[k] = min(500, max(5, self.qty.get(k, 25) + delta))

    def _buy(self, k):
        g = self.app.game
        qty = self.qty.get(k, 25)
        if g.buy(k, qty):
            self.app.notice(f"Bought {qty} {data.INGREDIENTS[k].name}.")
        else:
            self.app.notice("Can't afford that / no storage room.")

    def _draw_market(self, surf, r):
        g = self.app.game
        p = g.player
        col_w = r.width // 2 - S(8)
        # left: ingredient list
        sc = self._market_scroll
        sc.x, sc.y, sc.w, sc.h = r.x, r.y, col_w, r.height
        ings = list(data.INGREDIENTS)
        sc.content_h = S(4) + len(ings) * S(40)

        def draw_list(s):
            text(s, "INGREDIENT MARKET — tap + to adjust, Buy to stock",
                 13, theme.MUTED, (S(8), S(4)))
            yy = S(30)
            for k in ings:
                ing = data.INGREDIENTS[k]
                price = g.local_price(k)
                stock = p.stock(k)
                col = theme.GREEN if price <= ing.base * 0.85 else (
                    theme.RED if price >= ing.base * 1.35 else theme.TEXT)
                text(s, ing.name, 14, theme.TEXT, (S(8), yy))
                text(s, f"{money(price)}", 14, col, (S(150), yy))
                text(s, f"have {fmt(stock)}", 12, theme.MUTED, (S(215), yy + S(2)))
                q = self.qty.get(k, 25)
                text(s, f"{q}", 14, theme.ACCENT, (col_w - S(47), yy), center=True)
                yy += S(40)

        scroll_draw(surf, sc, draw_list)

        # right: district card + storage
        rx = r.x + col_w + S(16)
        card = pygame.Rect(rx, r.y, r.right - rx, r.height)
        w_profile, season = _season_weather(g)
        text(surf, f"{data.DISTRICTS[p.district].name}", 18, theme.TEXT,
             (rx, r.y + S(6)), bold=True)
        text(surf, f"{w_profile.name} · {season.name} · foot x{w_profile.foot:.2f}",
             13, theme.MUTED, (rx, r.y + S(34)))
        d = data.DISTRICTS[p.district]
        rows = [
            ("Demand", d.demand, 150),
            ("Competition", d.competition * 100, 100),
            ("Cost multiplier", d.cost_mult * 100, 100),
            ("Fuel to reach", d.fuel, 20),
        ]
        yy = r.y + S(64)
        for name, val, mx in rows:
            text(surf, name, 13, theme.MUTED, (rx, yy))
            bar(surf, pygame.Rect(rx + S(110), yy, S(160), S(12)), val / mx,
                _status_color(val / mx))
            text(surf, f"{val:.0f}" if mx >= 100 else f"{val:.2f}", 13, theme.TEXT,
                 (rx + S(285), yy))
            yy += S(26)
        yy += S(8)
        text(surf, "Storage", 13, theme.MUTED, (rx, yy))
        used = p.storage_used()
        cap = p.capacity()
        bar(surf, pygame.Rect(rx + S(90), yy, S(220), S(14)), used / cap, theme.ACCENT)
        text(surf, f"{used:.0f}/{cap}", 13, theme.TEXT, (rx + S(320), yy))
        yy += S(30)
        text(surf, "Weather & travel risk", 13, theme.MUTED, (rx, yy))
        yy += S(22)
        for line in wrap_text(
                "Weather shifts foot traffic and drink preferences. "
                "Prices differ per district — travel to arbitrage. "
                "Demographics each want a different flavour profile.",
                13, int((r.right - rx) * 0.9)):
            text(surf, line, 13, theme.FAINT, (rx, yy))
            yy += S(20)

    # ---------------- recipe ----------------

    def _panel_recipe(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        products = [k for k, pr in data.PRODUCTS.items()
                    if pr.requires is None or pr.requires in g.player.equipment]
        # product buttons (grid 2 cols)
        n = len(products)
        cols = 2
        gw = (w // 2 - S(20)) // cols
        gh = S(40)
        for i, k in enumerate(products):
            bx = x + (i % cols) * (gw + S(8))
            by = y + (i // cols) * (gh + S(6))
            b = Button(bx, by, gw, gh, data.PRODUCTS[k].name, accent=(k == g.active_product),
                       cb=lambda kk=k: self._select_product(kk), size=14)
            out.append(b)
        # sliders
        sy = y + ((n + cols - 1) // cols) * (gh + S(6)) + S(10)
        out.append(Slider(x, sy, w // 2 - S(60), "Sugar", value=g.recipe.sugar,
                          on_change=lambda v: self._set_slider("sugar", v)))
        out.append(Slider(x, sy + S(34), w // 2 - S(60), "Ice", value=g.recipe.ice,
                          on_change=lambda v: self._set_slider("ice", v)))
        out.append(Slider(x, sy + S(68), w // 2 - S(60), "Fruit", value=g.recipe.fruit,
                          on_change=lambda v: self._set_slider("fruit", v)))
        out.append(Toggle(x, sy + S(104), S(220), S(28), "Premium ingredients",
                          value=g.recipe.premium, cb=self._set_premium))
        # temperature
        product_hot = data.PRODUCTS[g.active_product].hot
        temps = ("cold", "extra_cold", "frozen") if not product_hot else ("hot", "warm")
        ty = sy + S(140)
        text_x = x
        out.append(Button(text_x, ty, S(110), S(30), TEMPS.get(g.recipe.temp, g.recipe.temp),
                          muted=True))
        tx = text_x + S(120)
        for t in temps:
            b = Button(tx, ty, S(96), S(30), TEMPS[t],
                       accent=(t == g.recipe.temp), cb=lambda tt=t: self._set_temp(tt))
            out.append(b)
            tx += S(104)
        # batch + produce
        py = sy + S(190)
        out.append(Button(x, py, S(40), S(36), "-", cb=lambda: self._batch(-10)))
        out.append(Button(x + S(46), py, S(100), S(36), f"{self.batch} cups", muted=True))
        out.append(Button(x + S(152), py, S(40), S(36), "+", cb=lambda: self._batch(10)))
        out.append(Button(x + S(210), py, w - S(210), S(40), "PRODUCE",
                          accent=True, cb=self._produce))
        return out

    def _select_product(self, k):
        g = self.app.game
        g.active_product = k
        g.recipe = Recipe(k, sugar=g.recipe.sugar, ice=g.recipe.ice,
                          fruit=g.recipe.fruit, premium=g.recipe.premium,
                          temp=None)
        self.app.notice(f"Now making {data.PRODUCTS[k].name}.")

    def _set_slider(self, which, v):
        g = self.app.game
        r = g.recipe
        if which == "sugar":
            r.sugar = v
        elif which == "ice":
            r.ice = v
        else:
            r.fruit = v

    def _set_premium(self, v):
        self.app.game.recipe.premium = v

    def _set_temp(self, t):
        self.app.game.recipe.temp = t

    def _batch(self, delta):
        self.batch = min(300, max(10, self.batch + delta))

    def _produce(self):
        g = self.app.game
        ok, msg = g.produce(self.batch)
        self.app.notice(msg)

    def _draw_recipe(self, surf, r):
        g = self.app.game
        recipe = g.recipe
        product = data.PRODUCTS[g.active_product]
        flavour = recipe.flavour(product)
        quality = recipe.quality(g, product, flavour)
        cost = recipe.cost_per_cup(g.local_price)
        # right stats card
        card_w = r.width // 2 - S(12)
        cx0 = r.x + r.width // 2 + S(8)
        text(surf, "RECIPE READOUT", 13, theme.MUTED, (cx0, r.y + S(6)))
        text(surf, f"{product.name} — {TEMPS.get(recipe.temp, recipe.temp)}",
             16, theme.TEXT, (cx0, r.y + S(28)), bold=True)
        text(surf, f"Cost / cup: {money(cost)}", 15, theme.MUTED, (cx0, r.y + S(54)))
        text(surf, f"Quality: {quality:.0f}/100", 15,
             _status_color(quality / 100), (cx0, r.y + S(80)))
        yy = r.y + S(112)
        text(surf, "Flavour profile", 13, theme.MUTED, (cx0, yy))
        yy += S(22)
        for dim in data.FLAVOUR_DIMS:
            text(surf, dim.capitalize(), 12, theme.FAINT, (cx0, yy))
            bar(surf, pygame.Rect(cx0 + S(80), yy, S(150), S(10)),
                flavour[dim] / 100.0, theme.ACCENT)
            text(surf, f"{flavour[dim]:.0f}", 12, theme.TEXT, (cx0 + S(240), yy))
            yy += S(20)
        yy += S(6)
        text(surf, "Ingredients / cup", 13, theme.MUTED, (cx0, yy))
        yy += S(22)
        for k, units in recipe.usage(product).items():
            text(surf, f"{data.INGREDIENTS[k].name} {fmt(units)}", 12, theme.FAINT,
                 (cx0, yy))
            yy += S(18)
        text(surf, "Tip: match the district's tastes and the weather.",
             12, theme.ORANGE, (cx0, r.bottom - S(24)))

    # ---------------- sell ----------------

    def _panel_sell(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        ref = reference_price(g)
        pmin, pmax = 0.25, 10.0
        frac = (g.price - pmin) / (pmax - pmin)
        sl = Slider(x, y + S(40), w // 2, "Price per cup",
                    value=frac * 100, step=1,
                    on_change=lambda v: self._price(v, pmin, pmax))
        out.append(sl)
        out.append(Button(x, y + S(90), S(150), S(40), "End Day", danger=True,
                          cb=self._end_day))
        # ads
        ay = y + S(150)
        adx = x
        for ad in data.ADS:
            b = Button(adx, ay, S(150), S(64), f"{ad.name} {money(ad.cost)}",
                       cb=lambda kk=ad.key: self._run_ad(kk), size=13)
            out.append(b)
            adx += S(160)
        return out

    def _price(self, v, pmin, pmax):
        g = self.app.game
        g.set_price(pmin + (pmax - pmin) * v / 100.0)

    def _run_ad(self, key):
        if self.app.game.run_ad(key):
            self.app.notice("Ad campaign started.")
        else:
            self.app.notice("Not enough cash for that ad.")

    def _draw_sell(self, surf, r):
        g = self.app.game
        p = g.player
        product = data.PRODUCTS[g.active_product]
        ref = reference_price(g)
        fore = g.forecast()
        text(surf, "SET PRICE & SELL", 13, theme.MUTED, (r.x, r.y + S(6)))
        text(surf, f"Reference: {money(ref)}", 14, theme.ACCENT, (r.x, r.y + S(18)))
        text(surf, f"Price now: {money(g.price)}", 18, theme.TEXT, (r.x + S(320), r.y + S(8)),
             bold=True)
        ratio = g.price / max(ref, 0.01)
        text(surf, f"{(ratio - 1) * 100:+.0f}% vs reference", 13,
             theme.GREEN if ratio <= 1 else theme.RED, (r.x + S(460), r.y + S(14)))
        # forecast card
        fx = r.x + r.width // 2 + S(12)
        text(surf, "FORECAST", 13, theme.MUTED, (fx, r.y + S(6)))
        rows = [
            ("Expected customers", fore["customers"]),
            ("Likely buyers", fore["buyers"]),
            ("Estimated revenue", money(fore["revenue"])),
            ("Stock ready", f"{fore['stock']:.0f} cups"),
            ("Quality", f"{fore['quality']:.0f}/100"),
        ]
        yy = r.y + S(30)
        for name, val in rows:
            text(surf, name, 14, theme.MUTED, (fx, yy))
            text(surf, str(val), 14, theme.TEXT, (fx + S(220), yy), right=True)
            yy += S(26)
        # ads
        ay = r.y + S(170)
        text(surf, "ADVERTISING — awareness: {:.0f}".format(p.awareness), 13,
             theme.MUTED, (r.x, ay))
        yy = ay + S(24)
        for ad in data.ADS:
            owned = any(a[0] == ad.key for a in g.ads_active)
            text(surf, ad.name, 13, theme.TEXT if not owned else theme.GREEN,
                 (r.x + S(4), yy))
            text(surf, f"{money(ad.cost)} · +{ad.awareness} aw · {ad.duration}d",
                 12, theme.FAINT, (r.x + S(150), yy))
            yy += S(24)
        text(surf, "End Day runs the sell phase: customers buy, spoilage, wages, "
                   "interest, taxes and events settle.",
             12, theme.FAINT, (r.x, r.bottom - S(30)))

    # ---------------- districts ----------------

    def _panel_districts(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        dkeys = list(data.DISTRICTS)
        cols = 2 if w > S(700) else 1
        gw = (w - (cols - 1) * S(10)) // cols
        gh = S(84)
        for i, k in enumerate(dkeys):
            bx = x + (i % cols) * (gw + S(10))
            by = y + (i // cols) * (gh + S(8))
            current = k == g.player.district
            b = Button(bx, by, gw, gh, data.DISTRICTS[k].name,
                       accent=current, muted=not current,
                       cb=lambda kk=k: self._travel(kk), size=15)
            b._dk = k
            if current:
                b.enabled = False
            out.append(b)
        return out

    def _travel(self, k):
        ok, msg = self.app.game.travel(k)
        self.app.notice(msg)
        if not ok:
            self.app.notice("Can't afford that trip.")

    def _draw_districts(self, surf, r):
        g = self.app.game
        cols = 2 if r.width > S(700) else 1
        gw = (r.width - (cols - 1) * S(10)) // cols
        gh = S(84)
        for i, (k, d) in enumerate(data.DISTRICTS.items()):
            bx = r.x + (i % cols) * (gw + S(10))
            by = r.y + (i // cols) * (gh + S(8))
            wkey = g.world.weather.get(k, "sunny")
            wp = data.WEATHER[wkey]
            text(surf, d.name, 14, theme.TEXT, (bx + S(8), by + S(6)), bold=True)
            text(surf, f"{wp.name} · demand {d.demand} · comp {d.competition:.2f} · "
                       f"cost x{d.cost_mult:.2f} · fuel {d.fuel}", 11, theme.MUTED,
                 (bx + S(8), by + S(26)))
            bar(surf, pygame.Rect(bx + S(8), by + S(46), gw - S(16), S(8)),
                d.demand / 150, theme.BLUE)
            cost = g.world.travel_cost(g.player.district, k, g)
            text(surf, f"travel {money(cost)}", 11,
                 theme.FAINT if k == g.player.district else theme.ACCENT,
                 (bx + S(8), by + S(60)))

    # ---------------- staff & upgrades ----------------

    def _panel_staff(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        eqs = list(data.EQUIPMENT.values())
        yy = y + S(4)
        for eq in eqs:
            owned = eq.key in g.player.equipment
            b = Button(x + S(260), yy, S(110), S(32), "Owned" if owned else "Buy",
                       accent=not owned, muted=owned,
                       cb=lambda kk=eq.key: self._buy_equip(kk))
            b.enabled = not owned
            out.append(b)
            yy += S(40)
        # tier upgrade
        nxt = data.TIERS[g.player.tier_idx + 1] if g.player.tier_idx + 1 < len(data.TIERS) else None
        if nxt:
            b = Button(x + S(540), y + S(4), S(200), S(36),
                       f"Upgrade → {nxt.name} ({money(nxt.cost)})", accent=True,
                       cb=self._upgrade)
            out.append(b)
        # insurance
        iy = y + S(300)
        for ins in data.INSURANCE_TYPES:
            on = ins["key"] in g.player.insurance
            out.append(Toggle(x + S(540), iy, S(280), S(30),
                              f"{ins['name']} ({money(ins['premium'])}/wk)",
                              value=on, cb=lambda v, kk=ins["key"]: self._ins(kk)))
            iy += S(36)
        # employees
        ey = y + S(460)
        for role, rd in data.EMPLOYEE_ROLES.items():
            emp = g.player.employees.get(role)
            lab = f"Hire {rd.name}" if not emp else f"Fire {rd.name}"
            out.append(Button(x + S(260), ey, S(120), S(32), lab,
                              danger=bool(emp), accent=not emp,
                              cb=lambda rr=role: self._hire(rr)))
            ey += S(38)
        return out

    def _buy_equip(self, k):
        if self.app.game.buy_equipment(k):
            self.app.notice(f"Bought the {data.EQUIPMENT[k].name}.")
        else:
            self.app.notice("Can't afford that (or missing a prerequisite).")

    def _upgrade(self):
        if self.app.game.upgrade_tier():
            self.app.notice("Upgraded your business!")
        else:
            self.app.notice("Not enough cash for the upgrade.")

    def _ins(self, k):
        if not self.app.game.toggle_insurance(k):
            self.app.notice("Not enough cash for the premium.")

    def _hire(self, role):
        g = self.app.game
        if role in g.player.employees:
            g.fire(role)
            self.app.notice("Employee let go.")
        elif g.hire(role):
            self.app.notice(f"Hired {data.EMPLOYEE_ROLES[role].name}.")
        else:
            self.app.notice("Can't afford that salary.")

    def _draw_staff(self, surf, r):
        g = self.app.game
        x, y = r.x, r.y
        text(surf, "EQUIPMENT", 13, theme.MUTED, (x, y + S(4)))
        yy = y + S(28)
        for eq in data.EQUIPMENT.values():
            owned = eq.key in g.player.equipment
            col = theme.GREEN if owned else theme.TEXT
            text(surf, eq.name, 14, col, (x + S(6), yy))
            text(surf, f"{money(eq.cost)}", 13, theme.MUTED, (x + S(190), yy))
            req = f" needs {data.EQUIPMENT[eq.requires].name}" if eq.requires else ""
            text(surf, eq.desc + req, 11, theme.FAINT, (x + S(6), yy + S(18)))
            yy += S(40)
        text(surf, "BUSINESS TIER", 13, theme.MUTED, (x + S(300), y + S(4)))
        t = g.player.tier()
        text(surf, f"{t.name} — {t.storage} storage, {t.max_serve} max/day",
             14, theme.TEXT, (x + S(300), y + S(28)))
        nxt = data.TIERS[g.player.tier_idx + 1] if g.player.tier_idx + 1 < len(data.TIERS) else None
        if nxt:
            text(surf, f"Next: {nxt.name} — {money(nxt.cost)}", 13, theme.ACCENT,
                 (x + S(300), y + S(52)))
        text(surf, "INSURANCE (weekly premiums, softens losses)", 13, theme.MUTED,
             (x + S(540), y + S(4)))
        iy = y + S(30)
        for ins in data.INSURANCE_TYPES:
            on = ins["key"] in g.player.insurance
            text(surf, ins["name"], 13, theme.GREEN if on else theme.MUTED,
                 (x + S(548), iy))
            text(surf, "covers: " + ", ".join(ins["covers"]), 11, theme.FAINT,
                 (x + S(548), iy + S(16)))
            iy += S(40)
        text(surf, "EMPLOYEES", 13, theme.MUTED, (x + S(300), y + S(90)))
        ey = y + S(116)
        for role, rd in data.EMPLOYEE_ROLES.items():
            emp = g.player.employees.get(role)
            if emp:
                text(surf, f"{rd.name}: skill {emp['skill']:.0f} morale {emp['morale']:.0f}",
                     13, theme.TEXT, (x + S(308), ey))
            else:
                text(surf, f"{rd.name}: {money(rd.salary)}/day", 13, theme.MUTED,
                     (x + S(308), ey))
            ey += S(34)

    # ---------------- finance ----------------

    def _panel_finance(self, area):
        g = self.app.game
        out = []
        x, y, w, h = area
        # loans
        yy = y + S(160)
        for opt in data.LOAN_OPTIONS:
            b = Button(x + S(260), yy, S(180), S(32), f"Borrow {money(opt.amount)}",
                       accent=True, cb=lambda kk=opt.key: self._loan(kk))
            out.append(b)
            yy += S(40)
        out.append(Button(x + S(260), yy, S(180), S(32), "Repay $500",
                          muted=True, cb=self._repay))
        return out

    def _loan(self, key):
        if self.app.game.take_loan(key):
            self.app.notice("Loan taken.")
        else:
            self.app.notice("Debt ceiling reached.")

    def _repay(self):
        if self.app.game.repay_loan(500):
            self.app.notice("Repaid $500.")
        else:
            self.app.notice("Nothing to repay / no cash.")

    def _draw_finance(self, surf, r):
        g = self.app.game
        p = g.player
        x, y = r.x, r.y
        text(surf, "BALANCE SHEET", 13, theme.MUTED, (x, y + S(4)))
        inv_val = p.inventory_value(g.market)
        eq_val = p.equipment_value()
        tier_val = p.tier_value()
        rows = [
            ("Cash", money(p.cash), theme.GREEN),
            ("Inventory value", money(inv_val), theme.TEXT),
            ("Equipment value", money(eq_val), theme.TEXT),
            ("Property (tier)", money(tier_val), theme.TEXT),
            ("Debt", money(p.debt), theme.RED),
            ("NET WORTH", money(g.net_worth()),
             theme.GREEN if g.net_worth() >= 0 else theme.RED),
        ]
        yy = y + S(28)
        for name, val, col in rows:
            text(surf, name, 14, theme.MUTED, (x + S(6), yy))
            text(surf, val, 15, col, (x + S(220), yy), right=True, bold=(name == "NET WORTH"))
            yy += S(26)
        yy += S(8)
        text(surf, "LOANS", 13, theme.MUTED, (x, yy))
        yy += S(24)
        if not p.loans:
            text(surf, "No loans. Debt free!", 13, theme.GREEN, (x + S(6), yy))
        else:
            for l in p.loans:
                text(surf, f"{money(l.principal)} @ {l.rate * 100:.1f}%/yr", 13,
                     theme.TEXT, (x + S(6), yy))
                yy += S(22)
        yy += S(8)
        text(surf, "CAMPAIGN STATS", 13, theme.MUTED, (x, yy))
        yy += S(24)
        st = g.stats
        srows = [
            ("Revenue", money(st["revenue"])),
            ("Expenses", money(st["expenses"])),
            ("Profit", money(st["profit"])),
            ("Interest paid", money(st["interest_paid"])),
            ("Taxes paid", money(st["taxes_paid"])),
            ("Customers served", st["customers"]),
            ("Products sold", st["sold"]),
            ("Repeat customers", st["repeat_customers"]),
            ("Best day profit", money(st["best_day_profit"])),
            ("Loans taken", st["loans_taken"]),
            ("Travel distance", st["travel_distance"]),
            ("Days played", st["days"]),
        ]
        for name, val in srows:
            text(surf, name, 13, theme.MUTED, (x + S(6), yy))
            text(surf, str(val), 13, theme.TEXT, (x + S(200), yy), right=True)
            yy += S(22)
        text(surf, "Weekly: 15% business tax, 5% payroll, 8% sales tax. "
                   "Payable days 7, 14, 21...",
             12, theme.ORANGE, (r.x, r.bottom - S(26)))

    # ---------------- news ----------------

    def _panel_news(self, area):
        sc = ScrollArea(area[0], area[1], area[2], area[3])
        self.scrolls[6] = sc
        sc.content_h = S(30) * (len(self.app.game.messages) + 4)
        return [sc]

    def _draw_news(self, surf, r):
        g = self.app.game
        sc = self.scrolls.get(6)
        if sc:
            sc.x, sc.y, sc.w, sc.h = r.x, r.y, r.width, r.height

        def draw_log(s):
            text(s, "MORNING NEWS", 13, theme.ACCENT, (S(8), S(4)))
            yy = S(24)
            for n in g.morning_news:
                for line in wrap_text(n, 13, int(r.width * 0.94)):
                    text(s, line, 13, theme.TEXT, (S(8), yy))
                    yy += S(18)
                yy += S(6)
            yy += S(10)
            text(s, "NEWS TICKER", 13, theme.MUTED, (S(8), yy))
            yy += S(22)
            for m in reversed(g.messages[-40:]):
                for line in wrap_text(m, 12, int(r.width * 0.94)):
                    text(s, line, 12, theme.FAINT, (S(8), yy))
                    yy += S(16)
                yy += S(4)
            text(s, "ACHIEVEMENTS", 13, theme.MUTED, (S(8), yy))
            yy += S(22)
            for a in ACHIEVEMENTS:
                owned = a["key"] in g.achievements
                text(s, ("✓ " if owned else "· ") + a["name"], 12,
                     theme.GREEN if owned else theme.FAINT, (S(8), yy))
                yy += S(18)

        scroll_draw(surf, sc, draw_log)


# ==========================================================================
# Report screen
# ==========================================================================

class ReportScreen:
    def __init__(self, app):
        self.app = app

    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            for b in self._widgets():
                if b.hit(ev.pos):
                    if b.label == "Next Day":
                        self.app.advance()
                    return True
        return False

    def _widgets(self):
        w, h = self.app.size
        return [Button(w // 2 - S(110), h - S(90), S(220), S(52), "Next Day",
                       accent=True, cb=None)]

    def draw(self, surf):
        g = self.app.game
        rpt = g.last_report or {}
        w, h = self.app.size
        s = theme.scale(w, h)
        surf.fill(theme.BG)
        text(surf, f"Day {g.day} — Night Report", int(30 * s), theme.TEXT,
             (w / 2, S(30)), center=True, bold=True)
        col_w = int(280 * s)
        x0 = w / 2 - col_w - S(10)
        y0 = S(80)
        left = [
            ("Customers", rpt.get("customers", 0)),
            ("Sold", rpt.get("sold", 0)),
            ("Turned away", rpt.get("lost", 0)),
            ("Revenue", money(rpt.get("revenue", 0))),
            ("Avg satisfaction", f"{rpt.get('avg_satisfaction', 0):.0f}/100"),
            ("Repeat customers", rpt.get("repeats", 0)),
            ("Quality", f"{rpt.get('quality', 0):.0f}/100"),
        ]
        right = [
            ("Spoilage", fmt(rpt.get("spoiled", 0))),
            ("Wages", money(rpt.get("wages", 0))),
            ("Loan interest", money(rpt.get("interest", 0))),
            ("Insurance", money(rpt.get("insurance", 0))),
            ("Taxes", money(rpt.get("taxes", 0))),
            ("Spent today", money(rpt.get("spent", 0))),
            ("DAY NET", money(rpt.get("net", 0))),
        ]
        for i, (name, val) in enumerate(left):
            yy = y0 + i * S(34)
            text(surf, name, 15, theme.MUTED, (x0, yy))
            text(surf, str(val), 15, theme.TEXT, (x0 + col_w, yy), right=True)
        x1 = w / 2 + S(10)
        for i, (name, val) in enumerate(right):
            yy = y0 + i * S(34)
            col = theme.GREEN if (name == "DAY NET" and rpt.get("net", 0) >= 0) else (
                theme.RED if name == "DAY NET" else theme.MUTED)
            text(surf, name, 15, col, (x1, yy))
            text(surf, str(val), 15, theme.TEXT if name != "DAY NET" else col,
                 (x1 + col_w, yy), right=True, bold=(name == "DAY NET"))
        night = rpt.get("night_event")
        if night:
            yy = S(360)
            text(surf, "Overnight:", 14, theme.ORANGE, (w / 2, yy), center=True)
            for line in wrap_text(night, 14, int(w * 0.7)):
                yy += S(22)
                text(surf, line, 14, theme.ORANGE, (w / 2, yy), center=True)
        for b in self._widgets():
            b.draw(surf)


# ==========================================================================
# End screen
# ==========================================================================

class EndScreen:
    def __init__(self, app):
        self.app = app

    def handle(self, ev) -> bool:
        if ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            for b in self._widgets():
                if b.hit(ev.pos):
                    if b.label == "New Campaign":
                        self.app.mode = "difficulty"
                    return True
        return False

    def _widgets(self):
        w, h = self.app.size
        return [Button(w / 2 - S(120), h - S(100), S(240), S(54), "New Campaign",
                       accent=True, cb=None)]

    def draw(self, surf):
        g = self.app.game
        w, h = self.app.size
        s = theme.scale(w, h)
        surf.fill(theme.BG)
        if g.won:
            title, col = "CAMPAIGN COMPLETE", theme.GREEN
        else:
            title, col = "BUSINESS CLOSED", theme.RED
        text(surf, title, int(44 * s), col, (w / 2, S(60)), center=True, bold=True)
        text(surf, g.end_reason.replace("_", " ").title(), int(18 * s), theme.TEXT,
             (w / 2, S(120)), center=True)
        text(surf, f"Final net worth: {money(g.net_worth())}", int(24 * s),
             theme.ACCENT, (w / 2, S(170)), center=True)
        st = g.stats
        rows = [
            ("Days played", st["days"]),
            ("Revenue", money(st["revenue"])),
            ("Customers served", st["customers"]),
            ("Products sold", st["sold"]),
            ("Best day profit", money(st["best_day_profit"])),
            ("Achievements", len(g.achievements)),
            ("Final reputation", f"{g.player.reputation:.0f}/100"),
            ("Highest title", g.title()),
        ]
        x0 = w / 2 - S(230)
        yy = S(230)
        for name, val in rows:
            text(surf, name, 16, theme.MUTED, (x0, yy))
            text(surf, str(val), 16, theme.TEXT, (x0 + S(330), yy), right=True)
            yy += S(34)
        for b in self._widgets():
            b.draw(surf)
