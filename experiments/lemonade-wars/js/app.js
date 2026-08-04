// Lemonade Wars — UI controller. Renders the GameState to DOM; no game
// logic lives here beyond presentation. Zero dependencies.
"use strict";

import { GameState } from "./sim.js";
import { Autoplay } from "./autoplay.js";
import { Recipe } from "./recipes.js";
import { EVENTS } from "./events.js";
import { ADS, DIFFICULTIES, DISTRICTS, EQUIPMENT, INGREDIENTS, INSURANCE_TYPES, LOAN_OPTIONS, PRODUCTS, TECH, TIERS, season_for_day } from "./data.js";
import { districtIdeal, expectedCustomers, productFit, referencePrice } from "./customers.js";

// Human-readable names for the event keys an insurance policy covers.
// Some covers keys are abbreviations (recall, inspection_fine, fraud, cyber)
// rather than event names — prettify those as a fallback.
const EVENT_NAME = {};
for (const ev of EVENTS) EVENT_NAME[ev.key] = ev.name;
const coversDesc = (covers) =>
  covers
    .map((k) => EVENT_NAME[k] ?? k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()))
    .join(", ");

const SAVE_KEY = "lemonade-wars-save";
const $ = (sel, root = document) => root.querySelector(sel);
const app = () => $("#app");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (v) => "$" + fmtNum(v);
const fmtNum = (v) => (Math.round(v * 100) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = (v) => Math.round(v).toLocaleString("en-US");
const pct = (v) => Math.round(v) + "%";
const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

let state = null; // GameState
let activeTab = "market";
let autoplayTimer = null;

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

function boot() {
  const saved = localStorage.getItem(SAVE_KEY);
  if (saved) {
    state = GameState.load(saved);
    if (state) {
      renderGame();
      return;
    }
  }
  renderTitle();
}

// ---------------------------------------------------------------------------
// Title screen
// ---------------------------------------------------------------------------

function renderTitle() {
  stopAutoplay();
  activeTab = "market";
  const saved = localStorage.getItem(SAVE_KEY);
  const savedExists = !!saved && !!GameState.load(saved);
  app().innerHTML = `
    <div class="screen">
      <div class="title-wrap">
        <div class="logo">🍋 Lemonade Wars</div>
        <div class="tagline">Run a lemonade empire across the city — market, weather, staff and finance.</div>
        <div class="difficulty-grid">
          ${Object.values(DIFFICULTIES).map((d, i) => `
            <div class="diff-card ${i === 1 ? "selected" : ""}" data-diff="${d.key}">
              <h3>${esc(d.name)}</h3>
              <p>${esc(d.desc)}</p>
              <div class="start">$${d.start_cash.toLocaleString()} · ${d.days} days</div>
            </div>`).join("")}
        </div>
        <div class="title-actions">
          <button class="primary" id="btn-start">Start Campaign</button>
          ${savedExists ? `<button id="btn-continue">Continue</button>` : ""}
          ${savedExists ? `<button class="muted-link" id="btn-wipe">Delete save</button>` : ""}
        </div>
      </div>
    </div>`;
  let chosen = DIFFICULTIES.normal.key;
  app().querySelectorAll(".diff-card").forEach((el) => {
    el.addEventListener("click", () => {
      app().querySelectorAll(".diff-card").forEach((x) => x.classList.remove("selected"));
      el.classList.add("selected");
      chosen = el.dataset.diff;
    });
  });
  $("#btn-start").addEventListener("click", () => {
    state = new GameState(chosen, Math.floor(Math.random() * 1e9));
    renderGame();
  });
  const cont = $("#btn-continue");
  if (cont) cont.addEventListener("click", () => renderGame());
  const wipe = $("#btn-wipe");
  if (wipe) wipe.addEventListener("click", () => {
    localStorage.removeItem(SAVE_KEY);
    renderTitle();
  });
}

// ---------------------------------------------------------------------------
// Game screen
// ---------------------------------------------------------------------------

function renderGame() {
  if (!state) return renderTitle();
  if (state.game_over) return renderEnd();

  const p = state.player;
  const d = state.difficulty;
  const season = season_for_day(state.day);
  const w = state.world.weatherAt(p.district);
  const nw = state.netWorth();
  const title = state.title();
  const dayTotal = state.campaignDayTotal();

  app().innerHTML = `
    <div class="screen">
      <div class="topbar">
        <div class="stat"><span class="label">Day</span><span class="value">${state.day}<span class="faint" style="font-size:0.8rem">/${dayTotal}</span></span></div>
        <div class="stat"><span class="label">Cash</span><span class="value ${p.cash < 0 ? "neg" : "pos"}">${money(p.cash)}</span></div>
        <div class="stat"><span class="label">Debt</span><span class="value ${p.debt > 0 ? "neg" : ""}">${money(p.debt)}</span></div>
        <div class="stat"><span class="label">Net worth</span><span class="value">${money(nw)}</span></div>
        <div class="stat"><span class="label">Reputation</span><span class="value">${Math.round(p.reputation)}</span></div>
        <div class="stat"><span class="label">Title</span><span class="value" style="font-size:0.95rem;color:var(--accent)">${esc(title)}</span></div>
        <div class="stat"><span class="label">Season</span><span class="value" style="font-size:0.9rem">${esc(season.name)}</span></div>
        <div class="stat"><span class="label">${esc(DISTRICTS[p.district].name)}</span><span class="value" style="font-size:0.85rem"><span class="chip ${w.key}">${esc(w.name)}</span></span></div>
        <div class="actions">
          <button id="btn-autoplay" title="Let the simulation run a few days">${autoplayTimer ? "Stop autoplay" : "Autoplay"}</button>
          <button id="btn-save">Save</button>
          <button id="btn-menu">Menu</button>
        </div>
      </div>

      <div class="tabs">
        ${TABS.map((t) => `<button class="tab ${activeTab === t.key ? "active" : ""}" data-tab="${t.key}">${t.label}</button>`).join("")}
      </div>

      <div id="tab-content"></div>

      <div class="panel" style="margin-top:14px">
        <h3>News</h3>
        <div class="news-log">
          ${state.morning_news.map((n) => `<div class="entry"><b>Today:</b> ${esc(n)}</div>`).join("")}
          ${state.messages.slice(-12).reverse().map((m) => {
            const m2 = m.replace(/^Day (\d+): /, "");
            const dnum = m.match(/^Day (\d+): /)?.[1] ?? "";
            return `<div class="entry"><span class="day">D${dnum}</span> ${esc(m2)}</div>`;
          }).join("")}
        </div>
      </div>
    </div>`;

  $("#btn-save").addEventListener("click", () => {
    state.save();
    localStorage.setItem(SAVE_KEY, state.save());
    flash("Saved.");
  });
  $("#btn-menu").addEventListener("click", () => renderTitle());
  $("#btn-autoplay").addEventListener("click", () => toggleAutoplay());

  app().querySelectorAll(".tab").forEach((el) => {
    el.addEventListener("click", () => {
      activeTab = el.dataset.tab;
      renderGame();
    });
  });

  renderTab();
}

const TABS = [
  { key: "market", label: "Market" },
  { key: "recipe", label: "Recipe" },
  { key: "sell", label: "Sell" },
  { key: "districts", label: "Districts" },
  { key: "staff", label: "Staff" },
  { key: "finance", label: "Finance" },
  { key: "news", label: "News" },
];

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

function renderTab() {
  const host = $("#tab-content");
  if (!host || !state) return;
  const tab = activeTab;
  if (tab === "market") renderMarket(host);
  else if (tab === "recipe") renderRecipe(host);
  else if (tab === "sell") renderSell(host);
  else if (tab === "districts") renderDistricts(host);
  else if (tab === "staff") renderStaff(host);
  else if (tab === "finance") renderFinance(host);
  else if (tab === "news") renderNews(host);
}

// --- Market ---------------------------------------------------------------

function renderMarket(host) {
  const p = state.player;
  const d0 = state.player.district;
  const rows = Object.entries(INGREDIENTS).map(([key, ing]) => {
    const price = state.localPrice(key);
    const stock = p.stock(key);
    const base = ing.base * DISTRICTS[d0].cost_mult;
    const deal = price < base * 0.85;
    return { key, ing, price, stock, base, deal };
  });

  const qtySel = (key) => `
    <div class="qty-control" data-ing="${key}">
      <button data-act="dec">−</button>
      <input type="number" min="1" step="1" value="10" style="width:64px">
      <button data-act="inc">+</button>
      <button class="primary" data-act="buy" style="padding:4px 10px">Buy</button>
    </div>`;

  host.innerHTML = `
    <div class="panel">
      <h3>Ingredient Market — ${esc(DISTRICTS[d0].name)}</h3>
      <p class="hint mb">Prices move daily with supply, season and events. Buying below the ${esc(DISTRICTS[d0].name)} baseline is a bargain. Storage: <b>${int(p.storageUsed())}/${int(p.capacity())}</b> units.</p>
      <table class="data">
        <thead><tr><th>Ingredient</th><th>Price/unit</th><th>Baseline</th><th>Stock</th><th></th></tr></thead>
        <tbody>
          ${rows.map(({ key, ing, price, stock, base, deal }) => `
            <tr>
              <td>${esc(ing.name)}</td>
              <td class="num ${deal ? "pos" : ""}">${fmtNum(price)}</td>
              <td class="num faint">${fmtNum(base)}</td>
              <td class="num">${stock ? fmtNum(stock) : "—"}</td>
              <td>${qtySel(key)}</td>
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;

  host.querySelectorAll("[data-ing]").forEach((ctl) => {
    const input = ctl.querySelector("input");
    ctl.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        const act = b.dataset.act;
        const ing = ctl.dataset.ing;
        let qty = parseInt(input.value, 10) || 1;
        if (act === "inc") qty += 10;
        else if (act === "dec") qty = Math.max(1, qty - 10);
        input.value = qty;
        if (act === "buy") {
          const ok = state.buy(ing, qty);
          if (!ok) flash("Can't buy that much right now.");
          renderGame();
        } else {
          input.value = qty;
        }
      });
    });
  });
}

// --- Recipe ---------------------------------------------------------------

function renderRecipe(host) {
  const p = state.player;
  const product = PRODUCTS[state.active_product];
  const r = state.recipe;

  const productButtons = Object.values(PRODUCTS).map((prod) => {
    const locked = prod.requires && !p.equipment.has(prod.requires);
    return `<button class="tab ${prod.key === state.active_product ? "active" : ""}" data-product="${prod.key}" ${locked ? "disabled title='Requires " + esc(EQUIPMENT[prod.requires].name) + "'" : ""}>
      ${esc(prod.name)}${locked ? " 🔒" : ""}</button>`;
  }).join("");

  const usage = r.usage(product);
  const perCup = Object.entries(usage).map(([k, u]) => `${esc(INGREDIENTS[k].name)} × ${g(u)}`).join(", ");
  const flavour = r.flavour(product);
  const quality = r.quality(state, product, flavour);
  const cost = r.costPerCup((ing) => state.localPrice(ing));
  const fit = productFit(state, flavour);

  const slider = (label, key, min, max, fmt) => `
    <div class="row slider-row">
      <span class="rowlabel">${label}</span>
      <input type="range" min="${min}" max="${max}" value="${r[key]}" data-slider="${key}">
      <span class="num" style="width:52px;text-align:right">${fmt ? fmt(r[key]) : r[key]}</span>
    </div>`;

  host.innerHTML = `
    <div class="panel">
      <h3>Recipe Designer</h3>
      <div class="tabs" style="margin-bottom:12px">${productButtons}</div>

      ${slider("Sugar", "sugar", 0, 100, (v) => v + "%")}
      ${slider("Ice", "ice", 0, 100, (v) => v + "%")}
      ${slider("Fruit", "fruit", 0, 100, (v) => v + "%")}

      <div class="row">
        <span class="rowlabel">Temperature</span>
        <select id="sel-temp">
          ${Object.entries(TEMPS).map(([k, name]) => `<option value="${k}" ${r.temp === k ? "selected" : ""}>${name}</option>`).join("")}
        </select>
      </div>
      <div class="row">
        <span class="rowlabel">Premium</span>
        <select id="sel-premium">
          <option value="0" ${r.premium ? "" : "selected"}>Standard</option>
          <option value="1" ${r.premium ? "selected" : ""}>Premium (organic + sweetener)</option>
        </select>
      </div>

      <div class="row">
        <span class="rowlabel"></span>
        <button class="primary" id="btn-apply">Apply recipe</button>
      </div>
    </div>

    <div class="panel">
      <h3>${esc(product.name)} — profile</h3>
      <div class="row"><span class="rowlabel">Per cup</span><span class="num">${perCup || "—"}</span></div>
      <div class="row"><span class="rowlabel">Cost/cup</span><span class="num">${fmtNum(cost)}</span></div>
      <div class="row"><span class="rowlabel">Quality</span><span class="num pos">${pct(quality)}</span></div>
      <div class="row"><span class="rowlabel">District fit</span><span class="num">${pct(fit)}</span></div>
      <div class="row">
        <span class="rowlabel">Flavour</span>
        <span class="num">${Object.entries(flavour).map(([k, v]) => `${k} ${pct(v)}`).join(" · ")}</span>
      </div>
      ${product.hot ? '<p class="hint mt">Hot drinks sell on cold days — watch the weather.</p>' : '<p class="hint mt">Cold drinks sell on hot days — watch the weather.</p>'}
    </div>`;

  host.querySelectorAll("[data-product]").forEach((b) => {
    b.addEventListener("click", () => {
      state.active_product = b.dataset.product;
      state.recipe = new Recipe(b.dataset.product);
      renderGame();
    });
  });
  host.querySelectorAll("[data-slider]").forEach((s) => {
    s.addEventListener("input", () => {
      const key = s.dataset.slider;
      const v = parseInt(s.value, 10);
      s.parentElement.querySelector(".num").textContent = v + "%";
      state.recipe[key] = v;
    });
  });
  $("#sel-temp").addEventListener("change", (e) => { state.recipe.temp = e.target.value; });
  $("#sel-premium").addEventListener("change", (e) => { state.recipe.premium = e.target.value === "1"; });
  $("#btn-apply").addEventListener("click", () => {
    state.setRecipe(state.recipe);
    flash("Recipe applied.");
    renderGame();
  });
}

const TEMPS = { cold: "Cold", extra_cold: "Extra Cold", frozen: "Frozen", hot: "Hot", warm: "Warm" };

// --- Sell -----------------------------------------------------------------

function renderSell(host) {
  const p = state.player;
  const product = PRODUCTS[state.active_product];
  const r = state.recipe;
  const stock = p.productStock(state.active_product);
  const forecast = state.forecast();
  const ref = referencePrice(state);

  host.innerHTML = `
    <div class="panel">
      <h3>Sell — ${esc(product.name)}</h3>
      <div class="row">
        <span class="rowlabel">Price per cup</span>
        <input type="number" id="in-price" min="0.25" max="99" step="0.05" value="${state.price.toFixed(2)}" style="width:100px">
        <button class="primary" id="btn-price">Set price</button>
        <span class="hint">reference ${fmtNum(ref)}</span>
      </div>
      <div class="row">
        <span class="rowlabel">Stock</span><span class="num">${stock ? int(stock) : "0"} cups</span>
      </div>
      <div class="row">
        <span class="rowlabel">Produce</span>
        <div class="qty-control">
          <button id="prod-dec">−</button>
          <input type="number" id="in-batch" min="1" value="20" style="width:64px">
          <button id="prod-inc">+</button>
          <button class="primary" id="btn-produce">Produce</button>
        </div>
      </div>
      <p class="hint mb">Production uses ${fmtNum(r.costPerCup((i) => state.localPrice(i)))} in ingredients per cup and stores ${pct(0)} of the recipe's ingredients.</p>
      <div class="row"><span class="rowlabel">Expected customers</span><span class="num">${int(forecast.customers)}</span></div>
      <div class="row"><span class="rowlabel">Expected buyers</span><span class="num">${int(forecast.buyers)}</span></div>
      <div class="row"><span class="rowlabel">Expected revenue</span><span class="num">${money(forecast.revenue)}</span></div>
      <div class="row"><span class="rowlabel">Product quality</span><span class="num pos">${pct(forecast.quality)}</span></div>
    </div>

    <div class="panel">
      <h3>End the day</h3>
      <p class="muted">Sell to customers, pay wages, interest and taxes, then see the night report.</p>
      <div class="row mt">
        <button class="primary" id="btn-endday">End Day ${state.day} →</button>
      </div>
    </div>`;

  $("#btn-price").addEventListener("click", () => {
    const v = parseFloat($("#in-price").value);
    if (!isNaN(v)) { state.setPrice(v); renderGame(); }
  });
  $("#in-price").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#btn-price").click(); });
  $("#btn-produce").addEventListener("click", () => {
    const v = parseInt($("#in-batch").value, 10) || 0;
    const [ok, msg] = state.produce(v);
    flash(ok ? msg : msg);
    renderGame();
  });
  $("#prod-inc").addEventListener("click", () => { $("#in-batch").value = (parseInt($("#in-batch").value, 10) || 1) + 10; });
  $("#prod-dec").addEventListener("click", () => { $("#in-batch").value = Math.max(1, (parseInt($("#in-batch").value, 10) || 1) - 10); });
  $("#btn-endday").addEventListener("click", () => {
    const report = state.endDay();
    renderReport(report);
  });
}

// --- Districts ------------------------------------------------------------

function renderDistricts(host) {
  const p = state.player;
  const current = p.district;
  const season = season_for_day(state.day);
  const rows = Object.values(DISTRICTS).map((d) => {
    const travel = state.world.travelCost(current, d.key, state);
    const canGo = d.key !== current && travel <= p.cash;
    const visited = p.visited.has(d.key);
    return `
      <tr>
        <td>${esc(d.name)} ${d.key === current ? '<span class="badge good">here</span>' : ""} ${visited ? '<span class="badge">visited</span>' : ""}</td>
        <td class="num">${pct(d.demand)}</td>
        <td class="num">${pct(d.competition)}</td>
        <td class="num">${fmtNum(d.cost_mult)}</td>
        <td class="num">${fmtNum(d.fuel)}</td>
        <td>
          ${d.key === current
            ? '<span class="faint">Current</span>'
            : `<button class="primary" data-go="${d.key}" ${canGo ? "" : "disabled"}>Travel (${fmtNum(travel)})</button>`}
        </td>
      </tr>`;
  }).join("");

  const ideal = districtIdeal(state);
  const w = state.world.weatherAt(current);

  host.innerHTML = `
    <div class="panel">
      <h3>Districts — ${esc(DISTRICTS[current].name)}</h3>
      <p class="hint mb">Demand is how busy the district is, competition is rivals cutting into it, cost_mult scales ingredient prices, fuel is the trip cost in fuel units.</p>
      <table class="data">
        <thead><tr><th>District</th><th>Demand</th><th>Competition</th><th>Cost ×</th><th>Fuel</th><th></th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h3>Local conditions — ${esc(DISTRICTS[current].name)}</h3>
      <div class="row"><span class="rowlabel">Weather</span><span class="chip ${w.key}">${esc(w.name)}</span></div>
      <div class="row"><span class="rowlabel">Season</span><span class="num">${esc(season.name)}</span></div>
      <div class="row"><span class="rowlabel">Ideal profile</span><span class="num">${Object.entries(ideal).map(([k, v]) => `${k} ${pct(v)}`).join(" · ")}</span></div>
    </div>`;

  host.querySelectorAll("[data-go]").forEach((b) => {
    b.addEventListener("click", () => {
      const [ok, msg] = state.travel(b.dataset.go);
      flash(ok ? msg : msg);
      renderGame();
    });
  });
}

// --- Staff ----------------------------------------------------------------

function renderStaff(host) {
  const p = state.player;
  const staffRows = Object.entries(EMPLOYEE_ROLES).map(([key, role]) => {
    const emp = p.employees[key];
    return `
      <tr>
        <td>${esc(role.name)}</td>
        <td class="num">$${fmtNum(role.salary)}/day</td>
        <td class="num">${emp ? fmtNum(emp.skill) : "—"}</td>
        <td class="num">${emp ? pct(emp.morale) : "—"}</td>
        <td>${emp
          ? `<button data-fire="${key}">Fire</button>`
          : `<button class="primary" data-hire="${key}" ${p.cash >= role.salary * 2 ? "" : "disabled"}>Hire</button>`}</td>
      </tr>`;
  }).join("");

  host.innerHTML = `
    <div class="panel">
      <h3>Staff</h3>
      <p class="hint mb">Staff cost a daily wage, add bonuses to service, quality and cleanliness, and morale drifts down slowly.</p>
      <table class="data">
        <thead><tr><th>Role</th><th>Wage</th><th>Skill</th><th>Morale</th><th></th></tr></thead>
        <tbody>${staffRows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h3>Equipment</h3>
      <table class="data">
        <thead><tr><th>Equipment</th><th>Cost</th><th>Effect</th><th></th></tr></thead>
        <tbody>
          ${Object.values(EQUIPMENT).map((eq) => {
            const owned = p.equipment.has(eq.key);
            const locked = eq.requires && !p.equipment.has(eq.requires);
            return `<tr>
              <td>${esc(eq.name)} ${owned ? '<span class="badge good">owned</span>' : ""}</td>
              <td class="num">${fmtNum(eq.cost)}</td>
              <td class="muted">${esc(eq.desc)}</td>
              <td>${owned ? '<span class="faint">—</span>' : `<button class="primary" data-buy-eq="${eq.key}" ${locked || eq.cost > p.cash ? "disabled" : ""}>Buy</button>`}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>
    <div class="panel">
      <h3>Technology</h3>
      <table class="data">
        <thead><tr><th>Tech</th><th>Cost</th><th>Effect</th><th></th></tr></thead>
        <tbody>
          ${Object.values(TECH).map((t) => {
            const owned = p.tech.has(t.key);
            const locked = t.requires && !p.tech.has(t.requires);
            return `<tr>
              <td>${esc(t.name)} ${owned ? '<span class="badge good">owned</span>' : ""}</td>
              <td class="num">${fmtNum(t.cost)}</td>
              <td class="muted">${esc(t.desc)}</td>
              <td>${owned ? '<span class="faint">—</span>' : `<button class="primary" data-buy-tech="${t.key}" ${locked || t.cost > p.cash ? "disabled" : ""}>Buy</button>`}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>`;

  host.querySelectorAll("[data-hire]").forEach((b) => {
    b.addEventListener("click", () => {
      const ok = state.hire(b.dataset.hire);
      if (!ok) flash("Can't hire right now.");
      renderGame();
    });
  });
  host.querySelectorAll("[data-fire]").forEach((b) => {
    b.addEventListener("click", () => {
      state.fire(b.dataset.fire);
      renderGame();
    });
  });
  host.querySelectorAll("[data-buy-eq]").forEach((b) => {
    b.addEventListener("click", () => {
      const ok = state.buyEquipment(b.dataset.buyEq);
      if (!ok) flash("Can't afford that.");
      renderGame();
    });
  });
  host.querySelectorAll("[data-buy-tech]").forEach((b) => {
    b.addEventListener("click", () => {
      const ok = state.buyTech(b.dataset.buyTech);
      if (!ok) flash("Can't afford that.");
      renderGame();
    });
  });
}

const EMPLOYEE_ROLES = {
  cashier: { name: "Cashier", salary: 45 },
  cook: { name: "Cook", salary: 60 },
  cleaner: { name: "Cleaner", salary: 40 },
  driver: { name: "Driver", salary: 55 },
};

// --- Finance --------------------------------------------------------------

function renderFinance(host) {
  const p = state.player;
  const next = state.campaignDayTotal() - state.day;

  const loanRows = p.loans.map((l, i) => `
    <tr>
      <td>Loan #${i + 1}</td>
      <td class="num">${fmtNum(l.principal)}</td>
      <td class="num">${pct(l.rate * 100)}</td>
      <td class="num">${fmtNum(l.principal * l.rate / 365)}</td>
    </tr>`).join("");

  const insRows = INSURANCE_TYPES.map((ins) => {
    const active = p.insurance.has(ins.key);
    return `<tr>
      <td>${esc(ins.name)}</td>
      <td class="muted">${esc(coversDesc(ins.covers))}</td>
      <td class="num">${fmtNum(ins.premium)}/wk</td>
      <td>${active ? `<button data-toggle-ins="${ins.key}">Cancel</button>` : `<button class="primary" data-toggle-ins="${ins.key}" ${p.cash >= ins.premium ? "" : "disabled"}>Take</button>`}</td>
    </tr>`;
  }).join("");

  host.innerHTML = `
    <div class="panel">
      <h3>Loans</h3>
      <table class="data">
        <thead><tr><th></th><th>Balance</th><th>Rate</th><th>Daily interest</th></tr></thead>
        <tbody>${loanRows || '<tr><td colspan="4" class="faint">No loans</td></tr>'}</tbody>
      </table>
      <div class="row mt">
        <span class="rowlabel">Take loan</span>
        <select id="sel-loan">${LOAN_OPTIONS.map((o) => `<option value="${o.key}">${esc(o.name)} ($${o.amount.toFixed(0)} @ ${pct(o.rate * 100)})</option>`).join("")}</select>
        <button class="primary" id="btn-loan">Borrow</button>
      </div>
      <div class="row">
        <span class="rowlabel">Repay</span>
        <input type="number" id="in-repay" min="0" step="50" value="0" style="width:100px">
        <button id="btn-repay">Repay</button>
      </div>
    </div>
    <div class="panel">
      <h3>Insurance</h3>
      <table class="data">
        <thead><tr><th>Cover</th><th>What it covers</th><th>Premium</th><th></th></tr></thead>
        <tbody>${insRows}</tbody>
      </table>
    </div>
    <div class="panel">
      <h3>Upgrades</h3>
      <table class="data">
        <thead><tr><th>Tier</th><th>Cost</th><th>Storage</th><th>Customers</th><th>Max serve</th><th></th></tr></thead>
        <tbody>
          ${TIERS.map((t, i) => {
            const cur = i === p.tier_idx;
            const nextTier = i === p.tier_idx + 1;
            const locked = i > p.tier_idx + 1;
            return `<tr>
              <td>${esc(t.name)} ${cur ? '<span class="badge good">current</span>' : ""}</td>
              <td class="num">${fmtNum(t.cost)}</td>
              <td class="num">${int(t.storage)}</td>
              <td class="num">${pct(t.cust_mult)}</td>
              <td class="num">${int(t.max_serve)}</td>
              <td>${nextTier ? `<button class="primary" id="btn-upgrade">Upgrade</button>` : locked ? '<span class="faint">locked</span>' : '<span class="faint">—</span>'}</td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    </div>`;

  $("#btn-loan").addEventListener("click", () => {
    const key = $("#sel-loan").value;
    const ok = state.takeLoan(key);
    if (!ok) flash("Loan limit reached.");
    renderGame();
  });
  $("#btn-repay").addEventListener("click", () => {
    const v = parseFloat($("#in-repay").value) || 0;
    const ok = state.repayLoan(v);
    if (!ok) flash("Nothing to repay.");
    renderGame();
  });
  host.querySelectorAll("[data-toggle-ins]").forEach((b) => {
    b.addEventListener("click", () => {
      const ok = state.toggleInsurance(b.dataset.toggleIns);
      if (!ok) flash("Can't afford that.");
      renderGame();
    });
  });
  const up = $("#btn-upgrade");
  if (up) up.addEventListener("click", () => {
    const ok = state.upgradeTier();
    if (!ok) flash("Can't afford that upgrade.");
    renderGame();
  });
}

// --- News ----------------------------------------------------------------

function renderNews(host) {
  const s = state.stats;
  const ach = [...state.achievements];
  host.innerHTML = `
    <div class="panel">
      <h3>News log</h3>
      <div class="news-log" style="max-height:380px">
        ${state.messages.slice().reverse().map((m) => {
          const m2 = m.replace(/^Day (\d+): /, "");
          const dnum = m.match(/^Day (\d+): /)?.[1] ?? "";
          return `<div class="entry"><span class="day">D${dnum}</span> ${esc(m2)}</div>`;
        }).join("") || '<div class="faint">Nothing yet.</div>'}
      </div>
    </div>
    <div class="panel">
      <h3>Campaign stats</h3>
      <div class="row"><span class="rowlabel">Days survived</span><span class="num">${int(s.days)}</span></div>
      <div class="row"><span class="rowlabel">Customers served</span><span class="num">${int(s.customers)}</span></div>
      <div class="row"><span class="rowlabel">Cups sold</span><span class="num">${int(s.sold)}</span></div>
      <div class="row"><span class="rowlabel">Repeat customers</span><span class="num">${int(s.repeat_customers)}</span></div>
      <div class="row"><span class="rowlabel">Total revenue</span><span class="num">${money(s.revenue)}</span></div>
      <div class="row"><span class="rowlabel">Total expenses</span><span class="num">${money(s.expenses)}</span></div>
      <div class="row"><span class="rowlabel">Ad spend</span><span class="num">${money(s.ad_spend)}</span></div>
      <div class="row"><span class="rowlabel">Interest paid</span><span class="num">${money(s.interest_paid)}</span></div>
      <div class="row"><span class="rowlabel">Taxes paid</span><span class="num">${money(s.taxes_paid)}</span></div>
      <div class="row"><span class="rowlabel">Best day profit</span><span class="num pos">${money(s.best_day_profit)}</span></div>
      <div class="row"><span class="rowlabel">Best day revenue</span><span class="num">${money(s.best_day_revenue)}</span></div>
      <div class="row"><span class="rowlabel">Loans taken</span><span class="num">${int(s.loans_taken)}</span></div>
      <div class="row"><span class="rowlabel">Events survived</span><span class="num">${int(s.events_survived)}</span></div>
      <div class="row"><span class="rowlabel">Best bargain</span><span class="num pos">${pct(s.best_bargain * 100)}</span></div>
    </div>
    <div class="panel">
      <h3>Achievements</h3>
      ${ach.length ? ach.map((a) => `<span class="achievement">🏆 ${esc(a)}</span>`).join("") : '<span class="faint">None yet — keep playing.</span>'}
    </div>`;
}

// ---------------------------------------------------------------------------
// Night report + end screen
// ---------------------------------------------------------------------------

function renderReport(report) {
  if (!report) return renderGame();
  const r = report;
  const w = WEATHER_NAMES[r.weather] ?? r.weather;
  const cards = [
    ["Customers", int(r.customers)],
    ["Sold", int(r.sold)],
    ["Lost", int(r.lost)],
    ["Revenue", money(r.revenue)],
    ["Satisfaction", pct(r.avg_satisfaction)],
    ["Repeats", int(r.repeats)],
    ["Spoiled", fmtNum(r.spoiled) + "u"],
    ["Wages", money(r.wages)],
    ["Interest", money(r.interest)],
    ["Taxes", money(r.taxes)],
    ["Day spend", money(r.spent)],
    ["Net", money(r.net)],
  ];

  app().innerHTML = `
    <div class="screen">
      <div class="report-head">
        <h2>Night Report — Day ${r.day}</h2>
        <span class="chip ${r.weather}">${esc(w)}</span>
        <div class="mt"><span class="badge ${r.net >= 0 ? "good" : "danger"}">${r.net >= 0 ? "Profit" : "Loss"} ${money(r.net)}</span></div>
      </div>
      <div class="report-grid">
        ${cards.map(([l, v]) => `<div class="report-card"><div class="l">${l}</div><div class="v ${l === "Net" ? (r.net >= 0 ? "pos" : "neg") : ""}">${v}</div></div>`).join("")}
      </div>
      ${r.night_event ? `<div class="panel"><h3>Night event</h3><p>${esc(r.night_event)}</p></div>` : ""}
      <div class="panel"><h3>Quality &amp; weather fit</h3>
        <div class="row"><span class="rowlabel">Product quality</span><span class="num">${pct(r.quality)}</span></div>
        <div class="row"><span class="rowlabel">Revenue / customers</span><span class="num">${r.customers ? fmtNum(r.revenue / r.customers) : "—"}</span></div>
      </div>
      <div class="row center" style="justify-content:center">
        <button class="primary" id="btn-next">${state.game_over ? "See results" : `Next Day →`}</button>
      </div>
    </div>`;

  $("#btn-next").addEventListener("click", () => {
    if (state.game_over) return renderEnd();
    state.nextDay();
    renderGame();
  });
}

const WEATHER_NAMES = {
  sunny: "Sunny", heat_wave: "Heat wave", humid: "Humid", rain: "Rain",
  thunderstorm: "Thunderstorm", windy: "Windy", cold_snap: "Cold snap", snow: "Snow",
};

function renderEnd() {
  stopAutoplay();
  const p = state.player;
  const s = state.stats;
  const win = state.won;
  const reason = state.end_reason === "campaign"
    ? `You survived all ${state.campaign_days} days.`
    : state.end_reason;

  app().innerHTML = `
    <div class="screen end-screen">
      <h1 class="${win ? "win" : "lose"}">${win ? "🏆 Campaign Complete!" : "💥 Business Closed"}</h1>
      <div class="end-reason">${esc(reason)}</div>
      <div class="end-stats">
        ${[
          ["Final cash", money(p.cash)],
          ["Debt", money(p.debt)],
          ["Net worth", money(state.netWorth())],
          ["Title", state.title()],
          ["Days", int(s.days)],
          ["Customers", int(s.customers)],
          ["Cups sold", int(s.sold)],
          ["Revenue", money(s.revenue)],
          ["Profit", money(s.profit)],
          ["Reputation", pct(p.reputation)],
        ].map(([l, v]) => `<div class="report-card"><div class="l">${l}</div><div class="v">${esc(v)}</div></div>`).join("")}
      </div>
      <div class="mb">
        ${[...state.achievements].map((a) => `<span class="achievement">🏆 ${esc(a)}</span>`).join("")}
      </div>
      <div class="title-actions">
        <button class="primary" id="btn-again">New Campaign</button>
        <button class="muted-link" id="btn-title">Title screen</button>
      </div>
    </div>`;

  localStorage.removeItem(SAVE_KEY);
  $("#btn-again").addEventListener("click", () => renderTitle());
  $("#btn-title").addEventListener("click", () => renderTitle());
}

// ---------------------------------------------------------------------------
// Autoplay + helpers
// ---------------------------------------------------------------------------

function toggleAutoplay() {
  if (autoplayTimer) { stopAutoplay(); renderGame(); return; }
  autoplayTimer = setInterval(() => {
    if (!state || state.game_over) { stopAutoplay(); renderGame(); return; }
    if (state.phase === "report") {
      state.nextDay();
      renderGame();
      return;
    }
    const ap = new Autoplay();
    ap.playDay(state);
    renderGame();
  }, 120);
}

function stopAutoplay() {
  if (autoplayTimer) {
    clearInterval(autoplayTimer);
    autoplayTimer = null;
  }
}

function flash(msg) {
  let el = $("#flash");
  if (!el) {
    el = document.createElement("div");
    el.id = "flash";
    el.style.cssText = "position:fixed;bottom:18px;left:50%;transform:translateX(-50%);background:var(--bg-elev);border:1px solid var(--border-strong);color:var(--text);padding:8px 16px;border-radius:8px;z-index:99;font-size:0.9rem;box-shadow:0 4px 20px rgba(0,0,0,0.4)";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = "1";
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.style.opacity = "0"; }, 2200);
}

function g(v) {
  return String(Math.round(v * 100) / 100);
}

boot();
