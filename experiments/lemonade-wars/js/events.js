// Random events: market movements, demand spikes, business setbacks and
// business-oriented "crime" — direct port of events.py. Every event returns
// the news headline the player sees.
"use strict";

import { ADVANCED, EQUIPMENT, INGREDIENTS, LUXURY, PRODUCTS } from "./data.js";

export const MULT = "mult";
export const DAYS = "days";

// --------------------------------------------------------------------------
// Event definitions
// --------------------------------------------------------------------------

export const EVENTS = [];

function _event(key, name, weight, kind, fn, min_day = 1) {
  EVENTS.push({ key, name, weight, kind, min_day, fn });
}

function _marketEvent(ing, mult, days) {
  const ings = Array.isArray(ing) ? ing : [ing];
  return function (game) {
    for (const k of ings) {
      game.market.setModifier(k, mult);
      game.market_events[k] = [mult, days];
    }
    const names = ings.map((k) => INGREDIENTS[k].name).join(", ");
    const pct = Math.round((mult - 1.0) * 100);
    const direction = mult > 1 ? "surge" : "drop";
    return `${names} prices ${direction} ${Math.abs(pct)}% for about ${days} days.`;
  };
}

function _demandEvent(nameKey, mult, days, text) {
  return function (game) {
    game.demand_modifiers[nameKey] = [mult, days];
    return text;
  };
}

// --- market events ---------------------------------------------------------

_event("lemon_shortage", "Lemon Shortage", 9, "market", _marketEvent("lemons", 2.3, 4));
_event("sugar_surplus", "Sugar Surplus", 8, "market", _marketEvent("sugar", 0.55, 4));
_event("ice_shortage", "Ice Shortage", 7, "market", _marketEvent("ice", 2.0, 3));
_event("coffee_boom", "Coffee Boom", 6, "market", _marketEvent("coffee", 1.8, 4));
_event("tea_shortage", "Tea Shortage", 6, "market", _marketEvent("tea", 1.9, 4));
_event("milk_surplus", "Milk Surplus", 5, "market", _marketEvent("milk", 0.6, 3));
_event("import_delays", "Import Delays", 6, "market", _marketEvent([...ADVANCED, ...LUXURY], 1.35, 3));
_event("crop_failure", "Crop Failure", 6, "market", _marketEvent(["strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"], 1.8, 4));
_event("fruit_glut", "Fruit Glut", 5, "market", _marketEvent(["strawberries", "mango", "lime"], 0.6, 3));
_event("fuel_spike", "Fuel Spike", 6, "market", (game) => _fuelEvent(game, 1.8, 3));
_event("organic_trend", "Organic Trend", 5, "demand",
  _demandEvent("organic_trend", 1.3, 4, "Health-conscious crowds are paying up for organic — demand is up 30% for a few days."));

function _fuelEvent(game, mult, days) {
  game.world.fuel_modifier = mult;
  game.demand_modifiers.fuel_spike = [mult, days];
  return `Fuel prices jumped ${Math.round((mult - 1) * 100)}% — travel will cost more for ${days} days.`;
}

// --- weather / demand events -----------------------------------------------

_event("heat_wave_streak", "Heat Wave", 6, "weather",
  _demandEvent("heat", 1.25, 3, "A heat wave has the city drinking ice-cold — cold drinks sell much better for a few days."));
_event("cold_front", "Cold Front", 5, "weather",
  _demandEvent("cold", 1.25, 3, "A cold front moved in — hot drinks are suddenly in demand."));
_event("tourist_boom", "Tourist Boom", 5, "demand",
  _demandEvent("tourist_boom", 1.35, 3, "Tourists are flooding the district — foot traffic up 35%."));
_event("food_festival", "Food Festival", 4, "demand",
  _demandEvent("festival", 1.40, 2, "A food festival has drawn a crowd — foot traffic up 40% for two days."));
_event("sporting_event", "Sporting Event", 4, "demand",
  _demandEvent("sport", 1.50, 1, "Big match today — the crowds are out in force (demand +50% today)."));
_event("music_festival", "Music Festival", 4, "demand",
  _demandEvent("music", 1.45, 2, "A music festival is in town — demand up 45% for two days."));
_event("celebrity_visit", "Celebrity Visit", 2, "demand",
  _demandEvent("celebrity", 1.60, 1, "A celebrity was spotted nearby — everyone wants a drink (demand +60% today)."));
_event("viral_post", "Viral Social Post", 3, "demand", (game) => _viral(game));

function _viral(game) {
  game.player.awareness = Math.min(120.0, game.player.awareness + 80);
  return "A customer's post about your stand went viral — awareness +80!";
}

// --- business events (resolved at day end) ---------------------------------

function _inspection(game) {
  const p = game.player;
  const effClean = Math.min(100.0, p.cleanliness + p.staffBonus("cleanliness"));
  if (effClean >= 70) {
    p.reputation = Math.min(100.0, p.reputation + 5);
    return "Health inspection passed with flying colours — reputation +5.";
  }
  let fine = 200.0;
  if (p.insurance.has("liability")) fine *= 0.5;
  p.cash = round2(p.cash - fine);
  p.reputation = Math.max(0.0, p.reputation - 10);
  game.health_fails += 1;
  return `Health inspection FAILED (cleanliness ${Math.floor(effClean)}/100). Fine $${fine.toFixed(0)}, reputation −10.`;
}

_event("health_inspection", "Health Inspection", 6, "business", _inspection, 4);
_event("competitor_discount", "Competitor Discount", 6, "business",
  _demandEvent("competitor_discount", 0.80, 2, "A rival vendor slashed prices — your demand dips 20% for two days."));
_event("ingredient_recall", "Ingredient Recall", 4, "business", (game) => _recall(game));
_event("supplier_bankrupt", "Supplier Bankruptcy", 4, "business", (game) => _supplierBankrupt(game));
_event("power_outage", "Power Outage", 4, "business", (game) => _powerOutage(game));
_event("theft", "Theft", 5, "crime", (game) => _crimeCash(game, 80.0, "The register was robbed overnight.", "business"));
_event("shoplifting", "Shoplifting", 5, "crime", (game) => _shoplifting(game));
_event("vandalism", "Vandalism", 4, "crime", (game) => _vandalism(game));
_event("equipment_theft", "Equipment Theft", 3, "crime", (game) => _equipmentTheft(game));
_event("counterfeit_coupons", "Counterfeit Coupons", 3, "crime", (game) => _crimeCash(game, 60.0, "Fake coupons drained the till.", "business"));
_event("supplier_scam", "Supplier Scam", 3, "crime", (game) => _crimeCash(game, 50.0, "A supplier took payment and never delivered.", "business"));
_event("cyber_attack", "Cyber Attack", 3, "crime", (game) => _cyber(game));

function _recall(game) {
  const p = game.player;
  const pool = Object.entries(p.inventory).filter(([, s]) => s.qty > 0).map(([k]) => k);
  if (!pool.length) return "An ingredient recall was announced — lucky you, none in stock.";
  const ing = game.rng.choice(pool);
  let loss = round3(p.inventory[ing].qty * 0.4);
  let value = loss * game.market.price(p.district, ing);
  p.inventory[ing].qty = round3(p.inventory[ing].qty - loss);
  if (p.insurance.has("inventory")) value *= 0.2;
  p.cash = round2(p.cash - value);
  return `Recall on ${INGREDIENTS[ing].name}: 40% tossed, $${value.toFixed(2)} lost.`;
}

function _supplierBankrupt(game) {
  const p = game.player;
  const pool = Object.entries(p.inventory).filter(([, s]) => s.qty > 0).map(([k]) => k);
  if (!pool.length) return "A supplier went bankrupt — nothing you carry was affected.";
  let lossValue = 0.0;
  for (const k of pool) {
    const qty = p.inventory[k].qty;
    lossValue += qty * game.market.price(p.district, k);
    delete p.inventory[k];
  }
  if (p.insurance.has("inventory")) lossValue *= 0.2;
  p.cash = round2(p.cash - lossValue);
  return `A key supplier went bankrupt — all their goods were seized ($${lossValue.toFixed(2)} lost).`;
}

function _powerOutage(game) {
  const p = game.player;
  let lost = 0.0;
  const chilled = new Set(["ice", "milk", "strawberries", "blueberries", "mango", "organic_fruit", "exotic_fruit"]);
  for (const [k, s] of Object.entries(p.inventory)) {
    if (!chilled.has(k)) continue;
    const drop = round3(s.qty * 0.08);
    s.qty = round3(s.qty - drop);
    lost += drop;
    if (s.qty <= 0.01) delete p.inventory[k];
  }
  return lost ? `Power outage: $${lost.toFixed(2)} worth of chilled stock ruined.` : "Power outage — nothing chilled was on hand.";
}

function _crimeCash(game, amount, text, coverKind) {
  const p = game.player;
  let loss = amount;
  if (p.insurance.has(coverKind)) loss *= 0.3;
  p.cash = round2(p.cash - loss);
  return `${text} Lost $${loss.toFixed(2)}.` + (p.insurance.has(coverKind) ? " (insurance covered 70%)" : "");
}

function _shoplifting(game) {
  const p = game.player;
  const pool = Object.entries(p.products).filter(([, s]) => s.qty > 0).map(([k]) => k);
  if (!pool.length) return "Shoplifters circled your stand — nothing was out to take.";
  const key = game.rng.choice(pool);
  const loss = Math.min(p.products[key].qty, 6.0);
  let value = loss * PRODUCTS[key].anchor * 0.7;
  p.products[key].qty = round3(p.products[key].qty - loss);
  if (p.insurance.has("inventory")) value *= 0.2;
  p.cash = round2(p.cash - value);
  return `Shoplifting: ${Math.floor(loss)} ${PRODUCTS[key].name}(s) gone ($${value.toFixed(2)} lost).`;
}

function _vandalism(game) {
  const p = game.player;
  let cost = 150.0;
  if (p.insurance.has("equipment")) cost *= 0.2;
  p.cash = round2(p.cash - cost);
  return `Vandals hit the stand — $${cost.toFixed(2)} in repairs.`;
}

function _equipmentTheft(game) {
  const p = game.player;
  const owned = [...p.equipment].filter((k) => k !== "squeezer");
  if (!owned.length) return "Thieves prowled but only found the squeezer — they left it.";
  const key = game.rng.choice(owned);
  if (p.insurance.has("equipment")) {
    p.cash = round2(p.cash - EQUIPMENT[key].cost * 0.2);
    return `Thieves tried to take the ${EQUIPMENT[key].name} — insurance covered it (deductible $${(EQUIPMENT[key].cost * 0.2).toFixed(0)}).`;
  }
  p.equipment.delete(key);
  return `The ${EQUIPMENT[key].name} was stolen! Buy a replacement.`;
}

function _cyber(game) {
  if (!(game.player.tech.size || Object.keys(game.player.employees).length)) {
    return "A phishing attempt hit the cart's tablet — nothing to take.";
  }
  let loss = 200.0;
  if (game.player.insurance.has("business")) loss *= 0.3;
  game.player.cash = round2(game.player.cash - loss);
  const covered = game.player.insurance.has("business") ? " (insurance covered 70%)" : "";
  return `Cyber attack on your systems — $${loss.toFixed(2)} lost.${covered}`;
}

// --- travel events ---------------------------------------------------------

export const TRAVEL_EVENTS = [];

function _travelEvent(key, name, weight, fn) {
  TRAVEL_EVENTS.push({ key, name, weight, fn });
}

_travelEvent("traffic_jam", "Traffic Jam", 25, (game) => _travelCost(game, 1.3, "Traffic jam — extra fuel burned."));
_travelEvent("road_construction", "Road Construction", 18, (game) => _travelCost(game, 1.5, "Detour around road construction — costly."));
_travelEvent("festival_parade", "Festival Parade", 12, (game) => _travelBonus(game, "You rolled in behind a festival parade — the district is buzzing."));
_travelEvent("flat_tire", "Flat Tire", 15, (game) => _travelPay(game, 40.0, "Flat tire — $40 for a roadside patch."));
_travelEvent("police_checkpoint", "Police Checkpoint", 12, (game) => _checkpoint(game));
_travelEvent("fuel_shortage", "Fuel Shortage", 10, (game) => _travelCost(game, 2.0, "Fuel shortage — prices through the roof."));
_travelEvent("vehicle_breakdown", "Vehicle Breakdown", 8, (game) => _travelPay(game, 80.0, "Breakdown — $80 tow and repair."));

function _travelCost(game, mult, text) {
  game.world.fuel_modifier *= mult;
  return `${text} (fuel ×${mult}).`;
}

function _travelPay(game, amount, text) {
  game.player.cash = round2(game.player.cash - amount);
  return `${text} −$${amount.toFixed(0)}.`;
}

function _travelBonus(game, text) {
  game.demand_modifiers.parade = [1.3, 1];
  return text + " Demand up 30% today.";
}

function _checkpoint(game) {
  if (game.player.reputation >= 45) {
    return "Police checkpoint waved you through — clean record, no trouble.";
  }
  const fine = 30.0;
  game.player.cash = round2(game.player.cash - fine);
  return `Police checkpoint — paperwork fine of $${fine.toFixed(0)}.`;
}

// --------------------------------------------------------------------------
// Rollers
// --------------------------------------------------------------------------

export function rollMorningEvent(game) {
  // One morning market/weather/demand headline, or None.
  const chance = 0.30 * game.difficulty.event_mult;
  if (game.rng.random() > chance) return null;
  const eligible = EVENTS.filter((e) => e.min_day <= game.day && (e.kind === "market" || e.kind === "weather" || e.kind === "demand"));
  const ev = game.rng.choices(eligible, eligible.map((e) => e.weight));
  return `${ev.name}: ${ev.fn(game)}`;
}

export function rollBusinessEvent(game) {
  const chance = 0.22 * game.difficulty.event_mult;
  if (game.rng.random() > chance) return null;
  const eligible = EVENTS.filter((e) => e.min_day <= game.day && (e.kind === "business" || e.kind === "crime"));
  const ev = game.rng.choices(eligible, eligible.map((e) => e.weight));
  return `${ev.name}: ${ev.fn(game)}`;
}

export function rollTravelEvent(game) {
  const w = game.world.weatherAt(game.player.district);
  const chance = (0.08 + w.travel_risk) * game.difficulty.event_mult;
  if (game.rng.random() > chance) return null;
  const ev = game.rng.choices(TRAVEL_EVENTS, TRAVEL_EVENTS.map((e) => e.weight));
  return `${ev.name}: ${ev.fn(game)}`;
}

// --------------------------------------------------------------------------
// Achievements
// --------------------------------------------------------------------------

export const ACHIEVEMENTS = [];

function _ach(key, name, desc, check) {
  ACHIEVEMENTS.push({ key, name, desc, check });
}

_ach("first_profit", "First Profit", "End a day in the black.", (g) => g.last_report && g.last_report.net > 0);
_ach("money_machine", "Money Machine", "Earn $300 in a single day.", (g) => g.last_report && g.last_report.revenue >= 300);
_ach("thousand_net", "On the Map", "Reach $1,000 net worth.", (g) => g.player.netWorth(g.market) >= 1000);
_ach("ten_thousand_net", "Real Business", "Reach $10,000 net worth.", (g) => g.player.netWorth(g.market) >= 10000);
_ach("hundred_thousand_net", "City Player", "Reach $100,000 net worth.", (g) => g.player.netWorth(g.market) >= 100000);
_ach("million_net", "Beverage Empire", "Reach $1,000,000 net worth.", (g) => g.player.netWorth(g.market) >= 1000000);
_ach("served_1000", "Thirsty City", "Serve 1,000 customers.", (g) => g.stats.customers >= 1000);
_ach("repeat_master", "Loyal Following", "Win 100 repeat customers.", (g) => g.stats.repeat_customers >= 100);
_ach("world_traveller", "On the Road", "Do business in 6 districts.", (g) => g.player.visited.size >= 6);
_ach("brand_loyal", "Household Name", "Reach 80 reputation.", (g) => g.player.reputation >= 80);
_ach("coffee_king", "Coffee King", "Sell 500 cups of coffee.", (g) => g.stats.sold >= 500 && g.active_product === "coffee");
_ach("hot_days", "Beat the Heat", "Sell on a heat-wave day.", (g) => g.last_report && g.last_report.weather === "heat_wave");
_ach("empire_builder", "Empire Builder", "Open a café or better.", (g) => g.player.tier_idx >= 4);
_ach("arbitrage", "Market Timer", "Buy ingredients at a 40%+ discount.", (g) => (g.stats.best_bargain ?? 0) >= 0.4);

export function checkAchievements(game) {
  const newOnes = [];
  for (const a of ACHIEVEMENTS) {
    if (!game.achievements.has(a.key) && a.check(game)) {
      game.achievements.add(a.key);
      newOnes.push(a.name);
    }
  }
  return newOnes;
}

const round2 = (v) => Math.round(v * 100) / 100;
const round3 = (v) => Math.round(v * 1000) / 1000;
