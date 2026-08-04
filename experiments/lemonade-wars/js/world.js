// World layer — direct port of world.py: seasons, per-district weather,
// fuel prices and travel (everything about *where* the player is).
"use strict";

import { DISTRICTS, season_for_day, WEATHER } from "./data.js";

export function rollWeather(rng, season, weatherMult = 1.0) {
  const weights = season.weather_weights;
  const keys = Object.keys(weights);
  const vals = Object.values(weights);
  return rng.choices(keys, vals);
}

export class World {
  constructor(rng, districts = null) {
    this.rng = rng;
    this.districts = districts || Object.keys(DISTRICTS);
    this.weather = {};
    this.fuel_price = 3.5;
    this.fuel_modifier = 1.0;
  }

  reset(day = 1, weatherMult = 1.0) {
    const season = season_for_day(day);
    const base = rollWeather(this.rng, season, weatherMult);
    for (const d of this.districts) {
      if (this.rng.random() < 0.20) {
        this.weather[d] = rollWeather(this.rng, season, weatherMult);
      } else {
        this.weather[d] = base;
      }
    }
  }

  dailyUpdate(day, weatherMult = 1.0) {
    const season = season_for_day(day);
    const base = rollWeather(this.rng, season, weatherMult);
    for (const d of this.districts) {
      if (this.rng.random() < 0.20) {
        this.weather[d] = rollWeather(this.rng, season, weatherMult);
      } else {
        this.weather[d] = base;
      }
    }
    // fuel price drifts, bounded
    this.fuel_price = round2(Math.min(Math.max(this.fuel_price * (1 + 0.05 * this.rng.gauss(0, 1)), 2.5), 6.0));
  }

  weatherAt(district) {
    return WEATHER[this.weather[district] ?? "sunny"];
  }

  travelCost(fromD, toD, game = null) {
    const dist = DISTRICTS[toD];
    let fuelUnits = dist.fuel;
    if (game !== null && game.player.equipment.has("delivery_vehicle")) fuelUnits *= 0.5;
    if (game !== null && game.player.employees.driver) fuelUnits *= 0.7;
    return round2(fuelUnits * this.fuel_price * this.fuel_modifier);
  }

  snapshot() {
    return { weather: this.weather, fuel_price: this.fuel_price, fuel_modifier: this.fuel_modifier };
  }

  static restore(rng, snap, districts = null) {
    const w = new World(rng, districts);
    w.weather = { ...snap.weather };
    w.fuel_price = Number(snap.fuel_price);
    w.fuel_modifier = Number(snap.fuel_modifier ?? 1.0);
    return w;
  }
}

const round2 = (v) => Math.round(v * 100) / 100;
