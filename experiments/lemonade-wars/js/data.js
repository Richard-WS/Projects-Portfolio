// Static game data — direct port of the Python core's data.py. Pure data,
// no randomness, no I/O. The simulation owns all state; this only defines
// the world the player plays in.
"use strict";

// ---------------------------------------------------------------------------
// Ingredients
// ---------------------------------------------------------------------------

export const INGREDIENTS = {
  // basic
  lemons: { key: "lemons", name: "Lemons", category: "basic", base: 0.25, vol: 0.16, shelf: 14, unit: "each" },
  sugar: { key: "sugar", name: "Sugar", category: "basic", base: 0.30, vol: 0.07, shelf: 60, unit: "portion" },
  ice: { key: "ice", name: "Ice", category: "basic", base: 0.10, vol: 0.22, shelf: 3, unit: "bag" },
  cups: { key: "cups", name: "Cups", category: "basic", base: 0.12, vol: 0.05, shelf: 120, unit: "pack" },
  water: { key: "water", name: "Water", category: "basic", base: 0.04, vol: 0.05, shelf: 30, unit: "L" },
  // advanced
  strawberries: { key: "strawberries", name: "Strawberries", category: "advanced", base: 0.60, vol: 0.20, shelf: 5, unit: "box" },
  blueberries: { key: "blueberries", name: "Blueberries", category: "advanced", base: 0.75, vol: 0.20, shelf: 4, unit: "box" },
  mango: { key: "mango", name: "Mango", category: "advanced", base: 0.85, vol: 0.18, shelf: 6, unit: "each" },
  lime: { key: "lime", name: "Lime", category: "advanced", base: 0.45, vol: 0.16, shelf: 10, unit: "each" },
  mint: { key: "mint", name: "Mint", category: "advanced", base: 0.50, vol: 0.18, shelf: 4, unit: "bunch" },
  honey: { key: "honey", name: "Honey", category: "advanced", base: 0.90, vol: 0.10, shelf: 240, unit: "jar" },
  vanilla: { key: "vanilla", name: "Vanilla", category: "advanced", base: 1.20, vol: 0.10, shelf: 240, unit: "bottle" },
  coffee: { key: "coffee", name: "Coffee", category: "advanced", base: 0.55, vol: 0.15, shelf: 90, unit: "bag" },
  tea: { key: "tea", name: "Tea", category: "advanced", base: 0.40, vol: 0.12, shelf: 180, unit: "box" },
  milk: { key: "milk", name: "Milk", category: "advanced", base: 0.50, vol: 0.15, shelf: 7, unit: "L" },
  sparkling_water: { key: "sparkling_water", name: "Sparkling Water", category: "advanced", base: 0.35, vol: 0.10, shelf: 60, unit: "bottle" },
  syrup: { key: "syrup", name: "Flavoured Syrup", category: "advanced", base: 0.70, vol: 0.10, shelf: 240, unit: "bottle" },
  // luxury
  organic_fruit: { key: "organic_fruit", name: "Organic Fruit", category: "luxury", base: 1.00, vol: 0.15, shelf: 5, unit: "box" },
  imported_citrus: { key: "imported_citrus", name: "Imported Citrus", category: "luxury", base: 1.20, vol: 0.15, shelf: 10, unit: "bag" },
  premium_sweetener: { key: "premium_sweetener", name: "Premium Sweetener", category: "luxury", base: 0.90, vol: 0.10, shelf: 120, unit: "jar" },
  exotic_fruit: { key: "exotic_fruit", name: "Exotic Fruit", category: "luxury", base: 1.40, vol: 0.18, shelf: 5, unit: "box" },
};

export const BASIC = Object.values(INGREDIENTS).filter((i) => i.category === "basic").map((i) => i.key);
export const ADVANCED = Object.values(INGREDIENTS).filter((i) => i.category === "advanced").map((i) => i.key);
export const LUXURY = Object.values(INGREDIENTS).filter((i) => i.category === "luxury").map((i) => i.key);

// ---------------------------------------------------------------------------
// Products and recipes
// ---------------------------------------------------------------------------

export const FLAVOUR_DIMS = ["sweet", "fresh", "acid", "refresh", "premium", "warm"];

export const PRODUCTS = {
  lemonade: {
    key: "lemonade", name: "Lemonade", anchor: 2.50,
    flavor: { sweet: 55, fresh: 60, acid: 40, refresh: 75, premium: 10, warm: 5 },
    base_recipe: { lemons: 2, sugar: 1.5, ice: 1.5, cups: 1, water: 1 },
  },
  pink_lemonade: {
    key: "pink_lemonade", name: "Pink Lemonade", anchor: 3.00,
    flavor: { sweet: 65, fresh: 65, acid: 35, refresh: 70, premium: 25, warm: 5 },
    base_recipe: { lemons: 2, strawberries: 1, sugar: 1.5, ice: 1.5, cups: 1, water: 1 },
  },
  limeade: {
    key: "limeade", name: "Limeade", anchor: 3.00,
    flavor: { sweet: 40, fresh: 70, acid: 80, refresh: 85, premium: 20, warm: 5 },
    base_recipe: { lime: 2, sugar: 1, ice: 1.5, cups: 1, water: 1 },
  },
  iced_tea: {
    key: "iced_tea", name: "Iced Tea", anchor: 2.25,
    flavor: { sweet: 30, fresh: 45, acid: 15, refresh: 70, premium: 15, warm: 5 },
    base_recipe: { tea: 1, sugar: 1, ice: 2, cups: 1, water: 1 },
  },
  sweet_tea: {
    key: "sweet_tea", name: "Sweet Tea", anchor: 2.50,
    flavor: { sweet: 85, fresh: 35, acid: 10, refresh: 60, premium: 15, warm: 10 },
    base_recipe: { tea: 1, sugar: 3, ice: 1.5, cups: 1, water: 1 },
  },
  coffee: {
    key: "coffee", name: "Coffee", anchor: 3.25,
    flavor: { sweet: 20, fresh: 40, acid: 30, refresh: 15, premium: 35, warm: 90 },
    base_recipe: { coffee: 1, milk: 0.5, water: 1, cups: 1 },
    requires: "coffee_machine", hot: true,
  },
  cold_brew: {
    key: "cold_brew", name: "Cold Brew", anchor: 3.75,
    flavor: { sweet: 15, fresh: 55, acid: 25, refresh: 40, premium: 45, warm: 5 },
    base_recipe: { coffee: 1.5, water: 1, cups: 1 },
    requires: "coffee_machine",
  },
  smoothie: {
    key: "smoothie", name: "Smoothie", anchor: 4.50,
    flavor: { sweet: 70, fresh: 80, acid: 25, refresh: 60, premium: 45, warm: 5 },
    base_recipe: { strawberries: 1, mango: 1, milk: 1, cups: 1 },
    requires: "blender",
  },
  fruit_punch: {
    key: "fruit_punch", name: "Fruit Punch", anchor: 4.00,
    flavor: { sweet: 75, fresh: 65, acid: 45, refresh: 80, premium: 40, warm: 5 },
    base_recipe: { exotic_fruit: 1, lemons: 1, sparkling_water: 1, cups: 1 },
    requires: "blender",
  },
  sparkling_lemonade: {
    key: "sparkling_lemonade", name: "Sparkling Lemonade", anchor: 3.50,
    flavor: { sweet: 55, fresh: 70, acid: 45, refresh: 90, premium: 35, warm: 5 },
    base_recipe: { lemons: 2, sugar: 1.5, sparkling_water: 2, cups: 1 },
    requires: "carbonator",
  },
};

// ---------------------------------------------------------------------------
// Demographics and districts
// ---------------------------------------------------------------------------

export const DEMOGRAPHICS = {
  students: {
    key: "students", name: "Students",
    pref: { sweet: 0.30, fresh: 0.15, acid: 0.10, refresh: 0.25, premium: 0.05, warm: 0.05 },
    taste: { sweet: 75, fresh: 55, acid: 35, refresh: 85, premium: 20, warm: 20 },
    price_sens: 0.70, quality_focus: 0.30,
  },
  office: {
    key: "office", name: "Office Workers",
    pref: { sweet: 0.15, fresh: 0.20, acid: 0.05, refresh: 0.10, premium: 0.20, warm: 0.30 },
    taste: { sweet: 40, fresh: 50, acid: 35, refresh: 35, premium: 55, warm: 85 },
    price_sens: 0.40, quality_focus: 0.60,
  },
  tourists: {
    key: "tourists", name: "Tourists",
    pref: { sweet: 0.20, fresh: 0.25, acid: 0.05, refresh: 0.25, premium: 0.20, warm: 0.05 },
    taste: { sweet: 60, fresh: 70, acid: 30, refresh: 85, premium: 70, warm: 25 },
    price_sens: 0.30, quality_focus: 0.70,
  },
  families: {
    key: "families", name: "Families",
    pref: { sweet: 0.30, fresh: 0.25, acid: 0.05, refresh: 0.20, premium: 0.10, warm: 0.10 },
    taste: { sweet: 70, fresh: 65, acid: 30, refresh: 60, premium: 35, warm: 35 },
    price_sens: 0.50, quality_focus: 0.50,
  },
  seniors: {
    key: "seniors", name: "Seniors",
    pref: { sweet: 0.25, fresh: 0.15, acid: 0.05, refresh: 0.10, premium: 0.10, warm: 0.35 },
    taste: { sweet: 65, fresh: 45, acid: 25, refresh: 35, premium: 25, warm: 85 },
    price_sens: 0.60, quality_focus: 0.40,
  },
  fitness: {
    key: "fitness", name: "Fitness Enthusiasts",
    pref: { sweet: 0.05, fresh: 0.40, acid: 0.10, refresh: 0.40, premium: 0.15, warm: 0.00 },
    taste: { sweet: 25, fresh: 90, acid: 40, refresh: 90, premium: 45, warm: 15 },
    price_sens: 0.35, quality_focus: 0.65,
  },
  children: {
    key: "children", name: "Children",
    pref: { sweet: 0.50, fresh: 0.15, acid: 0.05, refresh: 0.25, premium: 0.05, warm: 0.00 },
    taste: { sweet: 90, fresh: 50, acid: 20, refresh: 70, premium: 10, warm: 20 },
    price_sens: 0.80, quality_focus: 0.20,
  },
  professionals: {
    key: "professionals", name: "Professionals",
    pref: { sweet: 0.10, fresh: 0.20, acid: 0.05, refresh: 0.10, premium: 0.35, warm: 0.30 },
    taste: { sweet: 30, fresh: 55, acid: 35, refresh: 40, premium: 80, warm: 85 },
    price_sens: 0.20, quality_focus: 0.80,
  },
};

export const DISTRICTS = {
  downtown: {
    key: "downtown", name: "Downtown",
    mix: { office: 0.40, professionals: 0.20, tourists: 0.15, students: 0.10, seniors: 0.15 },
    demand: 120, competition: 0.50, crime: 0.50, cost_mult: 1.00, fuel: 0,
    blurb: "City hall, banks and the lunch crowd.",
  },
  business: {
    key: "business", name: "Business District",
    mix: { office: 0.60, professionals: 0.25, families: 0.05, seniors: 0.10 },
    demand: 110, competition: 0.60, crime: 0.30, cost_mult: 1.05, fuel: 8,
    blurb: "Suits, skyline and coffee on every corner.",
  },
  university: {
    key: "university", name: "University",
    mix: { students: 0.70, fitness: 0.15, professionals: 0.05, families: 0.10 },
    demand: 130, competition: 0.40, crime: 0.40, cost_mult: 0.90, fuel: 6,
    blurb: "Campus energy, tight budgets, huge volume.",
  },
  residential: {
    key: "residential", name: "Residential",
    mix: { families: 0.50, seniors: 0.25, children: 0.15, office: 0.10 },
    demand: 90, competition: 0.30, crime: 0.20, cost_mult: 0.95, fuel: 5,
    blurb: "Neighbourhood streets and family budgets.",
  },
  waterfront: {
    key: "waterfront", name: "Tourist Waterfront",
    mix: { tourists: 0.60, families: 0.15, fitness: 0.15, office: 0.10 },
    demand: 140, competition: 0.50, crime: 0.40, cost_mult: 1.15, fuel: 10,
    blurb: "Harbour views, high prices, deep pockets.",
  },
  stadium: {
    key: "stadium", name: "Stadium",
    mix: { tourists: 0.35, families: 0.30, students: 0.15, fitness: 0.20 },
    demand: 150, competition: 0.45, crime: 0.50, cost_mult: 1.10, fuel: 12,
    blurb: "Game days only — sell fast and loud.",
  },
  shopping: {
    key: "shopping", name: "Shopping Centre",
    mix: { families: 0.35, office: 0.25, professionals: 0.15, seniors: 0.15, children: 0.10 },
    demand: 130, competition: 0.55, crime: 0.35, cost_mult: 1.00, fuel: 9,
    blurb: "Malls, food courts and impulse buys.",
  },
  industrial: {
    key: "industrial", name: "Industrial Area",
    mix: { office: 0.40, professionals: 0.20, families: 0.25, seniors: 0.15 },
    demand: 80, competition: 0.35, crime: 0.60, cost_mult: 0.85, fuel: 7,
    blurb: "Cheap everything, hard to reach.",
  },
  park: {
    key: "park", name: "City Park",
    mix: { families: 0.35, fitness: 0.30, children: 0.20, seniors: 0.15 },
    demand: 100, competition: 0.30, crime: 0.25, cost_mult: 0.90, fuel: 6,
    blurb: "Weekend picnics and joggers.",
  },
  beach: {
    key: "beach", name: "Beach",
    mix: { tourists: 0.50, fitness: 0.25, families: 0.15, children: 0.10 },
    demand: 120, competition: 0.40, crime: 0.35, cost_mult: 1.20, fuel: 14,
    blurb: "Sunscreen economy — cold drinks rule.",
  },
};

export const START_DISTRICT = "downtown";

// ---------------------------------------------------------------------------
// Weather and seasons
// ---------------------------------------------------------------------------

export const WEATHER = {
  sunny: { key: "sunny", name: "Sunny", foot: 1.10, refresh_shift: 5, warm_shift: -5, spoilage: 1.00, travel_risk: 0.00 },
  cloudy: { key: "cloudy", name: "Cloudy", foot: 0.95, refresh_shift: 0, warm_shift: 0, spoilage: 1.00, travel_risk: 0.00 },
  windy: { key: "windy", name: "Windy", foot: 0.85, refresh_shift: -3, warm_shift: 2, spoilage: 1.00, travel_risk: 0.04 },
  rain: { key: "rain", name: "Rain", foot: 0.70, refresh_shift: -10, warm_shift: 8, spoilage: 1.00, travel_risk: 0.06 },
  thunderstorm: { key: "thunderstorm", name: "Thunderstorm", foot: 0.55, refresh_shift: -15, warm_shift: 12, spoilage: 1.05, travel_risk: 0.12 },
  heat_wave: { key: "heat_wave", name: "Heat Wave", foot: 1.25, refresh_shift: 25, warm_shift: -15, spoilage: 1.60, travel_risk: 0.02 },
  cold_snap: { key: "cold_snap", name: "Cold Snap", foot: 0.80, refresh_shift: -20, warm_shift: 25, spoilage: 1.00, travel_risk: 0.05 },
  humid: { key: "humid", name: "Humid", foot: 1.00, refresh_shift: 5, warm_shift: -2, spoilage: 1.20, travel_risk: 0.00 },
  snow: { key: "snow", name: "Snow", foot: 0.65, refresh_shift: -25, warm_shift: 30, spoilage: 1.00, travel_risk: 0.10 },
};

export const SEASONS = [
  { key: "spring", name: "Spring", weather_weights: { sunny: 30, cloudy: 25, windy: 20, rain: 15, humid: 10 }, refresh_shift: 5, warm_shift: 0, foot: 1.00 },
  { key: "summer", name: "Summer", weather_weights: { sunny: 35, humid: 20, heat_wave: 20, cloudy: 15, rain: 10 }, refresh_shift: 15, warm_shift: -10, foot: 1.20 },
  { key: "autumn", name: "Autumn", weather_weights: { cloudy: 30, windy: 25, rain: 20, sunny: 15, cold_snap: 10 }, refresh_shift: 0, warm_shift: 10, foot: 1.00 },
  { key: "winter", name: "Winter", weather_weights: { snow: 35, cold_snap: 30, cloudy: 20, sunny: 15 }, refresh_shift: -15, warm_shift: 25, foot: 0.80 },
];

export function season_for_day(day) {
  return SEASONS[((day - 1) / 30 | 0) % 4];
}

// ---------------------------------------------------------------------------
// Equipment, business tiers, technology
// ---------------------------------------------------------------------------

export const EQUIPMENT = {
  squeezer: { key: "squeezer", name: "Lemon Squeezer", cost: 150, desc: "Fresher citrus: +3 quality for citrus drinks, +10 storage.", requires: null },
  cash_register: { key: "cash_register", name: "Cash Register", cost: 500, desc: "Faster service: serves 15% more customers a day.", requires: null },
  juicer: { key: "juicer", name: "Juicer", cost: 800, desc: "+4 quality, +15 storage. Requires the squeezer.", requires: "squeezer" },
  coffee_machine: { key: "coffee_machine", name: "Coffee Machine", cost: 900, desc: "Unlocks Coffee and Cold Brew.", requires: null },
  carbonator: { key: "carbonator", name: "Carbonator", cost: 1000, desc: "Unlocks Sparkling Lemonade.", requires: null },
  blender: { key: "blender", name: "Blender", cost: 1200, desc: "Unlocks Smoothies and Fruit Punch.", requires: null },
  ice_machine: { key: "ice_machine", name: "Ice Machine", cost: 400, desc: "Ice costs 30% less; 30% less spoilage in heat.", requires: null },
  refrigeration: { key: "refrigeration", name: "Refrigeration", cost: 1500, desc: "Spoilage cut in half for ingredients and drinks.", requires: null },
  delivery_vehicle: { key: "delivery_vehicle", name: "Delivery Vehicle", cost: 2500, desc: "Travel fuel cost cut in half, +25 storage.", requires: null },
  storefront: { key: "storefront", name: "Storefront", cost: 5000, desc: "A fixed address: +40% customers in every district, +100 storage.", requires: null },
};

export const TIERS = [
  { key: "cart", name: "Lemonade Cart", cost: 0, storage: 900, max_serve: 120, cust_mult: 1.00 },
  { key: "trailer", name: "Food Trailer", cost: 3000, storage: 1400, max_serve: 250, cust_mult: 1.25 },
  { key: "food_truck", name: "Food Truck", cost: 8000, storage: 2000, max_serve: 450, cust_mult: 1.50 },
  { key: "kiosk", name: "Kiosk", cost: 15000, storage: 3000, max_serve: 700, cust_mult: 1.75 },
  { key: "cafe", name: "Café", cost: 40000, storage: 4500, max_serve: 1100, cust_mult: 2.00 },
  { key: "restaurant", name: "Restaurant", cost: 100000, storage: 7000, max_serve: 1800, cust_mult: 2.50 },
];

export const TECH = {
  online_ordering: { key: "online_ordering", name: "Online Ordering", cost: 3000, desc: "+15% daily customers.", requires: null },
  loyalty: { key: "loyalty", name: "Loyalty Program", cost: 2500, desc: "Repeat customers return 20% more often.", requires: null },
  delivery_app: { key: "delivery_app", name: "Delivery App", cost: 4500, desc: "+10% daily customers. Requires Online Ordering.", requires: "online_ordering" },
  inventory_automation: { key: "inventory_automation", name: "Inventory Automation", cost: 4000, desc: "Spoilage reduced by 20%.", requires: null },
  predictive_pricing: { key: "predictive_pricing", name: "Predictive Pricing", cost: 6000, desc: "Data-driven pricing: +5% revenue on sales.", requires: null },
};

// ---------------------------------------------------------------------------
// Employees
// ---------------------------------------------------------------------------

export const EMPLOYEE_ROLES = {
  cashier: { key: "cashier", name: "Cashier", salary: 45, desc: "Faster service, +10% customers served." },
  cook: { key: "cook", name: "Cook", salary: 60, desc: "Better drinks: +6 quality." },
  driver: { key: "driver", name: "Driver", salary: 50, desc: "Travel fuel costs 30% less." },
  cleaner: { key: "cleaner", name: "Cleaner", salary: 40, desc: "Higher cleanliness — health inspections pass easily." },
};

// ---------------------------------------------------------------------------
// Loans, advertising, insurance
// ---------------------------------------------------------------------------

export const LOAN_OPTIONS = [
  { key: "small", name: "Small Loan", amount: 1000, rate: 0.10 },
  { key: "expansion", name: "Expansion Loan", amount: 5000, rate: 0.09 },
  { key: "emergency", name: "Emergency Loan", amount: 2000, rate: 0.16 },
];

export const ADS = [
  { key: "flyers", name: "Flyers", cost: 25, awareness: 12, duration: 1 },
  { key: "signs", name: "Signs", cost: 75, awareness: 25, duration: 3 },
  { key: "social", name: "Social Media", cost: 120, awareness: 35, duration: 2 },
  { key: "newspaper", name: "Newspaper", cost: 250, awareness: 50, duration: 2 },
  { key: "radio", name: "Local Radio", cost: 300, awareness: 60, duration: 3 },
  { key: "influencer", name: "Influencers", cost: 600, awareness: 100, duration: 4 },
  { key: "billboard", name: "Billboards", cost: 900, awareness: 140, duration: 7 },
  { key: "tv", name: "TV Spot", cost: 2000, awareness: 250, duration: 5 },
];

export const INSURANCE_TYPES = [
  { key: "equipment", name: "Equipment", premium: 15, covers: ["vandalism", "equipment_theft"] },
  { key: "inventory", name: "Inventory", premium: 12, covers: ["shoplifting", "recall"] },
  { key: "liability", name: "Liability", premium: 10, covers: ["inspection_fine"] },
  { key: "business", name: "Business", premium: 20, covers: ["fraud", "cyber"] },
];

// ---------------------------------------------------------------------------
// Difficulties
// ---------------------------------------------------------------------------

export const DIFFICULTIES = {
  relaxed: { key: "relaxed", name: "Relaxed", desc: "Cheap loans, calm markets, 150 days.", loan_mult: 0.6, event_mult: 0.6, competitor_mult: 0.7, patience: 1.3, weather_mult: 0.8, days: 150, start_cash: 750 },
  normal: { key: "normal", name: "Normal", desc: "The intended experience, 120 days.", loan_mult: 1.0, event_mult: 1.0, competitor_mult: 1.0, patience: 1.0, weather_mult: 1.0, days: 120, start_cash: 500 },
  hard: { key: "hard", name: "Hard", desc: "Tighter money, smarter crowds, 100 days.", loan_mult: 1.4, event_mult: 1.3, competitor_mult: 1.2, patience: 0.8, weather_mult: 1.2, days: 100, start_cash: 400 },
  expert: { key: "expert", name: "Expert", desc: "Ruthless. 90 days to build an empire.", loan_mult: 1.8, event_mult: 1.6, competitor_mult: 1.4, patience: 0.6, weather_mult: 1.4, days: 90, start_cash: 300 },
  simulation: { key: "simulation", name: "Simulation", desc: "Endless sandbox on Normal rules.", loan_mult: 1.0, event_mult: 1.0, competitor_mult: 1.0, patience: 1.0, weather_mult: 1.0, days: null, start_cash: 500 },
};

// ---------------------------------------------------------------------------
// Campaign / endgame
// ---------------------------------------------------------------------------

export const TITLES = [
  [1000000, "Beverage Empire"],
  [500000, "Regional Tycoon"],
  [200000, "City Brand"],
  [75000, "Local Favourite"],
  [20000, "Corner Stand"],
  [5000, "Street Vendor"],
];

export const CAMPAIGN_LENGTH = 120;
export const START_CASH = 500.0;
export const START_LOAN = 2000.0;
export const START_LOAN_RATE = 0.09;
export const START_REPUTATION = 20.0;
export const MAX_DEBT = 6000.0;
export const CASH_FLOOR = -500.0;

export const BANKRUPTCY_REASONS = {
  debt: "Total debt exceeded the bank's ceiling.",
  cash: "Cash ran out and the bills could not be paid.",
  health: "Repeated health-code failures forced the cart to close.",
};

export const STAT_KEYS = [
  "days", "revenue", "profit", "expenses", "customers", "repeat_customers",
  "sold", "lost_sales", "bought_units", "ad_spend", "travel_distance",
  "loans_taken", "interest_paid", "taxes_paid", "spoiled_units",
  "recipes_created", "batches", "districts_visited", "events_survived",
  "best_day_profit", "best_day_revenue",
];
