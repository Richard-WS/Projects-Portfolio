"""Static game data: ingredients, products, districts, weather, seasons,
equipment, business tiers, technology, employees, loans, advertising,
difficulties and campaign metadata.

Everything here is pure data — no randomness, no I/O. The simulation in
sim.py owns all state; this module only defines the world the player plays in.
"""

from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# Ingredients
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Ingredient:
    key: str
    name: str
    category: str            # basic | advanced | luxury
    base: float              # reference price per unit
    vol: float               # daily volatility (std dev of the price walk)
    shelf: int               # shelf life in days
    unit: str                # display unit

    @property
    def pmin(self) -> float:
        return round(self.base * 0.5, 2)

    @property
    def pmax(self) -> float:
        return round(self.base * 2.4, 2)


INGREDIENTS: dict[str, Ingredient] = {
    # basic
    "lemons":         Ingredient("lemons", "Lemons", "basic", 0.25, 0.16, 14, "each"),
    "sugar":          Ingredient("sugar", "Sugar", "basic", 0.30, 0.07, 60, "portion"),
    "ice":            Ingredient("ice", "Ice", "basic", 0.10, 0.22, 3, "bag"),
    "cups":           Ingredient("cups", "Cups", "basic", 0.12, 0.05, 120, "pack"),
    "water":          Ingredient("water", "Water", "basic", 0.04, 0.05, 30, "L"),
    # advanced
    "strawberries":   Ingredient("strawberries", "Strawberries", "advanced", 0.60, 0.20, 5, "box"),
    "blueberries":    Ingredient("blueberries", "Blueberries", "advanced", 0.75, 0.20, 4, "box"),
    "mango":          Ingredient("mango", "Mango", "advanced", 0.85, 0.18, 6, "each"),
    "lime":           Ingredient("lime", "Lime", "advanced", 0.45, 0.16, 10, "each"),
    "mint":           Ingredient("mint", "Mint", "advanced", 0.50, 0.18, 4, "bunch"),
    "honey":          Ingredient("honey", "Honey", "advanced", 0.90, 0.10, 240, "jar"),
    "vanilla":        Ingredient("vanilla", "Vanilla", "advanced", 1.20, 0.10, 240, "bottle"),
    "coffee":         Ingredient("coffee", "Coffee", "advanced", 0.55, 0.15, 90, "bag"),
    "tea":            Ingredient("tea", "Tea", "advanced", 0.40, 0.12, 180, "box"),
    "milk":           Ingredient("milk", "Milk", "advanced", 0.50, 0.15, 7, "L"),
    "sparkling_water": Ingredient("sparkling_water", "Sparkling Water", "advanced", 0.35, 0.10, 60, "bottle"),
    "syrup":          Ingredient("syrup", "Flavoured Syrup", "advanced", 0.70, 0.10, 240, "bottle"),
    # luxury
    "organic_fruit":  Ingredient("organic_fruit", "Organic Fruit", "luxury", 1.00, 0.15, 5, "box"),
    "imported_citrus": Ingredient("imported_citrus", "Imported Citrus", "luxury", 1.20, 0.15, 10, "bag"),
    "premium_sweetener": Ingredient("premium_sweetener", "Premium Sweetener", "luxury", 0.90, 0.10, 120, "jar"),
    "exotic_fruit":   Ingredient("exotic_fruit", "Exotic Fruit", "luxury", 1.40, 0.18, 5, "box"),
}

BASIC = [k for k, i in INGREDIENTS.items() if i.category == "basic"]
ADVANCED = [k for k, i in INGREDIENTS.items() if i.category == "advanced"]
LUXURY = [k for k, i in INGREDIENTS.items() if i.category == "luxury"]


# --------------------------------------------------------------------------
# Products and recipes
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Product:
    key: str
    name: str
    anchor: float                    # reference selling price
    flavor: dict                     # target vector over flavour dimensions
    base_recipe: dict                # ingredient key -> units per cup
    requires: str | None = None      # equipment key that gates production
    hot: bool = False
    icon: str = ""


# flavour dimensions used everywhere:
FLAVOUR_DIMS = ("sweet", "fresh", "acid", "refresh", "premium", "warm")

PRODUCTS: dict[str, Product] = {
    "lemonade": Product("lemonade", "Lemonade", 2.50,
        {"sweet": 55, "fresh": 60, "acid": 40, "refresh": 75, "premium": 10, "warm": 5},
        {"lemons": 2, "sugar": 1.5, "ice": 1.5, "cups": 1, "water": 1}),
    "pink_lemonade": Product("pink_lemonade", "Pink Lemonade", 3.00,
        {"sweet": 65, "fresh": 65, "acid": 35, "refresh": 70, "premium": 25, "warm": 5},
        {"lemons": 2, "strawberries": 1, "sugar": 1.5, "ice": 1.5, "cups": 1, "water": 1}),
    "limeade": Product("limeade", "Limeade", 3.00,
        {"sweet": 40, "fresh": 70, "acid": 80, "refresh": 85, "premium": 20, "warm": 5},
        {"lime": 2, "sugar": 1, "ice": 1.5, "cups": 1, "water": 1}),
    "iced_tea": Product("iced_tea", "Iced Tea", 2.25,
        {"sweet": 30, "fresh": 45, "acid": 15, "refresh": 70, "premium": 15, "warm": 5},
        {"tea": 1, "sugar": 1, "ice": 2, "cups": 1, "water": 1}),
    "sweet_tea": Product("sweet_tea", "Sweet Tea", 2.50,
        {"sweet": 85, "fresh": 35, "acid": 10, "refresh": 60, "premium": 15, "warm": 10},
        {"tea": 1, "sugar": 3, "ice": 1.5, "cups": 1, "water": 1}),
    "coffee": Product("coffee", "Coffee", 3.25,
        {"sweet": 20, "fresh": 40, "acid": 30, "refresh": 15, "premium": 35, "warm": 90},
        {"coffee": 1, "milk": 0.5, "water": 1, "cups": 1}, requires="coffee_machine", hot=True),
    "cold_brew": Product("cold_brew", "Cold Brew", 3.75,
        {"sweet": 15, "fresh": 55, "acid": 25, "refresh": 40, "premium": 45, "warm": 5},
        {"coffee": 1.5, "water": 1, "cups": 1}, requires="coffee_machine"),
    "smoothie": Product("smoothie", "Smoothie", 4.50,
        {"sweet": 70, "fresh": 80, "acid": 25, "refresh": 60, "premium": 45, "warm": 5},
        {"strawberries": 1, "mango": 1, "milk": 1, "cups": 1}, requires="blender"),
    "fruit_punch": Product("fruit_punch", "Fruit Punch", 4.00,
        {"sweet": 75, "fresh": 65, "acid": 45, "refresh": 80, "premium": 40, "warm": 5},
        {"exotic_fruit": 1, "lemons": 1, "sparkling_water": 1, "cups": 1}, requires="blender"),
    "sparkling_lemonade": Product("sparkling_lemonade", "Sparkling Lemonade", 3.50,
        {"sweet": 55, "fresh": 70, "acid": 45, "refresh": 90, "premium": 35, "warm": 5},
        {"lemons": 2, "sugar": 1.5, "sparkling_water": 2, "cups": 1}, requires="carbonator"),
}


# --------------------------------------------------------------------------
# Demographics and districts
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Demographic:
    key: str
    name: str
    pref: dict                       # weight per flavour dimension (0..1)
    taste: dict                      # target flavour vector (0..100)
    price_sens: float                # 0 (indifferent) .. 1 (very sensitive)
    quality_focus: float             # how much quality matters to them


DEMOGRAPHICS: dict[str, Demographic] = {
    "students": Demographic("students", "Students",
        {"sweet": 0.30, "fresh": 0.15, "acid": 0.10, "refresh": 0.25, "premium": 0.05, "warm": 0.05},
        {"sweet": 75, "fresh": 55, "acid": 35, "refresh": 85, "premium": 20, "warm": 20}, 0.70, 0.30),
    "office": Demographic("office", "Office Workers",
        {"sweet": 0.15, "fresh": 0.20, "acid": 0.05, "refresh": 0.10, "premium": 0.20, "warm": 0.30},
        {"sweet": 40, "fresh": 50, "acid": 35, "refresh": 35, "premium": 55, "warm": 85}, 0.40, 0.60),
    "tourists": Demographic("tourists", "Tourists",
        {"sweet": 0.20, "fresh": 0.25, "acid": 0.05, "refresh": 0.25, "premium": 0.20, "warm": 0.05},
        {"sweet": 60, "fresh": 70, "acid": 30, "refresh": 85, "premium": 70, "warm": 25}, 0.30, 0.70),
    "families": Demographic("families", "Families",
        {"sweet": 0.30, "fresh": 0.25, "acid": 0.05, "refresh": 0.20, "premium": 0.10, "warm": 0.10},
        {"sweet": 70, "fresh": 65, "acid": 30, "refresh": 60, "premium": 35, "warm": 35}, 0.50, 0.50),
    "seniors": Demographic("seniors", "Seniors",
        {"sweet": 0.25, "fresh": 0.15, "acid": 0.05, "refresh": 0.10, "premium": 0.10, "warm": 0.35},
        {"sweet": 65, "fresh": 45, "acid": 25, "refresh": 35, "premium": 25, "warm": 85}, 0.60, 0.40),
    "fitness": Demographic("fitness", "Fitness Enthusiasts",
        {"sweet": 0.05, "fresh": 0.40, "acid": 0.10, "refresh": 0.40, "premium": 0.15, "warm": 0.00},
        {"sweet": 25, "fresh": 90, "acid": 40, "refresh": 90, "premium": 45, "warm": 15}, 0.35, 0.65),
    "children": Demographic("children", "Children",
        {"sweet": 0.50, "fresh": 0.15, "acid": 0.05, "refresh": 0.25, "premium": 0.05, "warm": 0.00},
        {"sweet": 90, "fresh": 50, "acid": 20, "refresh": 70, "premium": 10, "warm": 20}, 0.80, 0.20),
    "professionals": Demographic("professionals", "Professionals",
        {"sweet": 0.10, "fresh": 0.20, "acid": 0.05, "refresh": 0.10, "premium": 0.35, "warm": 0.30},
        {"sweet": 30, "fresh": 55, "acid": 35, "refresh": 40, "premium": 80, "warm": 85}, 0.20, 0.80),
}


@dataclass(frozen=True)
class District:
    key: str
    name: str
    mix: dict                        # demographic key -> share
    demand: float                    # base daily customers
    competition: float               # 0..1
    crime: float                     # 0..1
    cost_mult: float                 # ingredient price multiplier
    fuel: float                      # travel cost in fuel units
    blurb: str


DISTRICTS: dict[str, District] = {
    "downtown": District("downtown", "Downtown",
        {"office": 0.40, "professionals": 0.20, "tourists": 0.15, "students": 0.10, "seniors": 0.15},
        120, 0.50, 0.50, 1.00, 0,
        "City hall, banks and the lunch crowd."),
    "business": District("business", "Business District",
        {"office": 0.60, "professionals": 0.25, "families": 0.05, "seniors": 0.10},
        110, 0.60, 0.30, 1.05, 8,
        "Suits, skyline and coffee on every corner."),
    "university": District("university", "University",
        {"students": 0.70, "fitness": 0.15, "professionals": 0.05, "families": 0.10},
        130, 0.40, 0.40, 0.90, 6,
        "Campus energy, tight budgets, huge volume."),
    "residential": District("residential", "Residential",
        {"families": 0.50, "seniors": 0.25, "children": 0.15, "office": 0.10},
        90, 0.30, 0.20, 0.95, 5,
        "Neighbourhood streets and family budgets."),
    "waterfront": District("waterfront", "Tourist Waterfront",
        {"tourists": 0.60, "families": 0.15, "fitness": 0.15, "office": 0.10},
        140, 0.50, 0.40, 1.15, 10,
        "Harbour views, high prices, deep pockets."),
    "stadium": District("stadium", "Stadium",
        {"tourists": 0.35, "families": 0.30, "students": 0.15, "fitness": 0.20},
        150, 0.45, 0.50, 1.10, 12,
        "Game days only — sell fast and loud."),
    "shopping": District("shopping", "Shopping Centre",
        {"families": 0.35, "office": 0.25, "professionals": 0.15, "seniors": 0.15, "children": 0.10},
        130, 0.55, 0.35, 1.00, 9,
        "Malls, food courts and impulse buys."),
    "industrial": District("industrial", "Industrial Area",
        {"office": 0.40, "professionals": 0.20, "families": 0.25, "seniors": 0.15},
        80, 0.35, 0.60, 0.85, 7,
        "Cheap everything, hard to reach."),
    "park": District("park", "City Park",
        {"families": 0.35, "fitness": 0.30, "children": 0.20, "seniors": 0.15},
        100, 0.30, 0.25, 0.90, 6,
        "Weekend picnics and joggers."),
    "beach": District("beach", "Beach",
        {"tourists": 0.50, "fitness": 0.25, "families": 0.15, "children": 0.10},
        120, 0.40, 0.35, 1.20, 14,
        "Sunscreen economy — cold drinks rule."),
}

START_DISTRICT = "downtown"


# --------------------------------------------------------------------------
# Weather and seasons
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class WeatherProfile:
    key: str
    name: str
    foot: float                      # foot-traffic multiplier
    refresh_shift: float             # preference shift toward refreshment
    warm_shift: float                # preference shift toward warmth
    spoilage: float                  # spoilage multiplier
    travel_risk: float               # extra travel-event chance


WEATHER: dict[str, WeatherProfile] = {
    "sunny": WeatherProfile("sunny", "Sunny", 1.10, 5, -5, 1.00, 0.00),
    "cloudy": WeatherProfile("cloudy", "Cloudy", 0.95, 0, 0, 1.00, 0.00),
    "windy": WeatherProfile("windy", "Windy", 0.85, -3, 2, 1.00, 0.04),
    "rain": WeatherProfile("rain", "Rain", 0.70, -10, 8, 1.00, 0.06),
    "thunderstorm": WeatherProfile("thunderstorm", "Thunderstorm", 0.55, -15, 12, 1.05, 0.12),
    "heat_wave": WeatherProfile("heat_wave", "Heat Wave", 1.25, 25, -15, 1.60, 0.02),
    "cold_snap": WeatherProfile("cold_snap", "Cold Snap", 0.80, -20, 25, 1.00, 0.05),
    "humid": WeatherProfile("humid", "Humid", 1.00, 5, -2, 1.20, 0.00),
    "snow": WeatherProfile("snow", "Snow", 0.65, -25, 30, 1.00, 0.10),
}


@dataclass(frozen=True)
class Season:
    key: str
    name: str
    weather_weights: dict            # weather key -> weight
    refresh_shift: float             # seasonal preference shift
    warm_shift: float
    foot: float


SEASONS: list[Season] = [
    Season("spring", "Spring",
        {"sunny": 30, "cloudy": 25, "windy": 20, "rain": 15, "humid": 10}, 5, 0, 1.00),
    Season("summer", "Summer",
        {"sunny": 35, "humid": 20, "heat_wave": 20, "cloudy": 15, "rain": 10}, 15, -10, 1.20),
    Season("autumn", "Autumn",
        {"cloudy": 30, "windy": 25, "rain": 20, "sunny": 15, "cold_snap": 10}, 0, 10, 1.00),
    Season("winter", "Winter",
        {"snow": 35, "cold_snap": 30, "cloudy": 20, "sunny": 15}, -15, 25, 0.80),
]


def season_for_day(day: int) -> Season:
    """Day 1 starts in spring; a full campaign year wraps."""
    return SEASONS[((day - 1) // 30) % 4]


# --------------------------------------------------------------------------
# Equipment, business tiers, technology
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Equipment:
    key: str
    name: str
    cost: float
    desc: str
    requires: str | None = None


EQUIPMENT: dict[str, Equipment] = {
    "squeezer": Equipment("squeezer", "Lemon Squeezer", 150,
        "Fresher citrus: +3 quality for citrus drinks, +10 storage.", None),
    "cash_register": Equipment("cash_register", "Cash Register", 500,
        "Faster service: serves 15% more customers a day.", None),
    "juicer": Equipment("juicer", "Juicer", 800,
        "+4 quality, +15 storage. Requires the squeezer.", "squeezer"),
    "coffee_machine": Equipment("coffee_machine", "Coffee Machine", 900,
        "Unlocks Coffee and Cold Brew.", None),
    "carbonator": Equipment("carbonator", "Carbonator", 1000,
        "Unlocks Sparkling Lemonade.", None),
    "blender": Equipment("blender", "Blender", 1200,
        "Unlocks Smoothies and Fruit Punch.", None),
    "ice_machine": Equipment("ice_machine", "Ice Machine", 400,
        "Ice costs 30% less; 30% less spoilage in heat.", None),
    "refrigeration": Equipment("refrigeration", "Refrigeration", 1500,
        "Spoilage cut in half for ingredients and drinks.", None),
    "delivery_vehicle": Equipment("delivery_vehicle", "Delivery Vehicle", 2500,
        "Travel fuel cost cut in half, +25 storage.", None),
    "storefront": Equipment("storefront", "Storefront", 5000,
        "A fixed address: +40% customers in every district, +100 storage.", None),
}


@dataclass(frozen=True)
class Tier:
    key: str
    name: str
    cost: float
    storage: int
    max_serve: int                   # hard cap on daily customers served
    cust_mult: float                 # customer multiplier


TIERS: list[Tier] = [
    Tier("cart", "Lemonade Cart", 0, 900, 120, 1.00),
    Tier("trailer", "Food Trailer", 3000, 1400, 250, 1.25),
    Tier("food_truck", "Food Truck", 8000, 2000, 450, 1.50),
    Tier("kiosk", "Kiosk", 15000, 3000, 700, 1.75),
    Tier("cafe", "Café", 40000, 4500, 1100, 2.00),
    Tier("restaurant", "Restaurant", 100000, 7000, 1800, 2.50),
]


@dataclass(frozen=True)
class Tech:
    key: str
    name: str
    cost: float
    desc: str
    requires: str | None = None


TECH: dict[str, Tech] = {
    "online_ordering": Tech("online_ordering", "Online Ordering", 3000,
        "+15% daily customers.", None),
    "loyalty": Tech("loyalty", "Loyalty Program", 2500,
        "Repeat customers return 20% more often.", None),
    "delivery_app": Tech("delivery_app", "Delivery App", 4500,
        "+10% daily customers. Requires Online Ordering.", "online_ordering"),
    "inventory_automation": Tech("inventory_automation", "Inventory Automation", 4000,
        "Spoilage reduced by 20%.", None),
    "predictive_pricing": Tech("predictive_pricing", "Predictive Pricing", 6000,
        "Data-driven pricing: +5% revenue on sales.", None),
}


# --------------------------------------------------------------------------
# Employees
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class EmployeeRole:
    key: str
    name: str
    salary: float
    desc: str


EMPLOYEE_ROLES: dict[str, EmployeeRole] = {
    "cashier": EmployeeRole("cashier", "Cashier", 45, "Faster service, +10% customers served."),
    "cook": EmployeeRole("cook", "Cook", 60, "Better drinks: +6 quality."),
    "driver": EmployeeRole("driver", "Driver", 50, "Travel fuel costs 30% less."),
    "cleaner": EmployeeRole("cleaner", "Cleaner", 40, "Higher cleanliness — health inspections pass easily."),
}


# --------------------------------------------------------------------------
# Loans, advertising, insurance
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class LoanOption:
    key: str
    name: str
    amount: float
    rate: float                      # annual interest, before reputation modifier


LOAN_OPTIONS: list[LoanOption] = [
    LoanOption("small", "Small Loan", 1000, 0.10),
    LoanOption("expansion", "Expansion Loan", 5000, 0.09),
    LoanOption("emergency", "Emergency Loan", 2000, 0.16),
]


@dataclass(frozen=True)
class AdCampaign:
    key: str
    name: str
    cost: float
    awareness: float
    duration: int


ADS: list[AdCampaign] = [
    AdCampaign("flyers", "Flyers", 25, 12, 1),
    AdCampaign("signs", "Signs", 75, 25, 3),
    AdCampaign("social", "Social Media", 120, 35, 2),
    AdCampaign("newspaper", "Newspaper", 250, 50, 2),
    AdCampaign("radio", "Local Radio", 300, 60, 3),
    AdCampaign("influencer", "Influencers", 600, 100, 4),
    AdCampaign("billboard", "Billboards", 900, 140, 7),
    AdCampaign("tv", "TV Spot", 2000, 250, 5),
]


INSURANCE_TYPES: list[dict] = [
    {"key": "equipment", "name": "Equipment", "premium": 15, "covers": ["vandalism", "equipment_theft"]},
    {"key": "inventory", "name": "Inventory", "premium": 12, "covers": ["shoplifting", "recall"]},
    {"key": "liability", "name": "Liability", "premium": 10, "covers": ["inspection_fine"]},
    {"key": "business", "name": "Business", "premium": 20, "covers": ["fraud", "cyber"]},
]


# --------------------------------------------------------------------------
# Difficulties
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Difficulty:
    key: str
    name: str
    desc: str
    loan_mult: float
    event_mult: float
    competitor_mult: float
    patience: float                  # customer price tolerance multiplier
    weather_mult: float
    days: int | None                 # None = endless (Simulation)
    start_cash: float


DIFFICULTIES: dict[str, Difficulty] = {
    "relaxed": Difficulty("relaxed", "Relaxed", "Cheap loans, calm markets, 150 days.", 0.6, 0.6, 0.7, 1.3, 0.8, 150, 750),
    "normal": Difficulty("normal", "Normal", "The intended experience, 120 days.", 1.0, 1.0, 1.0, 1.0, 1.0, 120, 500),
    "hard": Difficulty("hard", "Hard", "Tighter money, smarter crowds, 100 days.", 1.4, 1.3, 1.2, 0.8, 1.2, 100, 400),
    "expert": Difficulty("expert", "Expert", "Ruthless. 90 days to build an empire.", 1.8, 1.6, 1.4, 0.6, 1.4, 90, 300),
    "simulation": Difficulty("simulation", "Simulation", "Endless sandbox on Normal rules.", 1.0, 1.0, 1.0, 1.0, 1.0, None, 500),
}


# --------------------------------------------------------------------------
# Campaign / endgame
# --------------------------------------------------------------------------

TITLES: list[tuple[float, str]] = [
    (1_000_000, "Beverage Empire"),
    (500_000, "Regional Tycoon"),
    (200_000, "City Brand"),
    (75_000, "Local Favourite"),
    (20_000, "Corner Stand"),
    (5_000, "Street Vendor"),
]

CAMPAIGN_LENGTH = 120               # used when a difficulty has no explicit days
START_CASH = 500.0
START_LOAN = 2000.0                 # the initial business loan, 9% annual
START_LOAN_RATE = 0.09
START_REPUTATION = 20.0
MAX_DEBT = 6000.0                   # absolute debt ceiling before bankruptcy
CASH_FLOOR = -500.0                 # deeper than this = can't pay the bills

BANKRUPTCY_REASONS = {
    "debt": "Total debt exceeded the bank's ceiling.",
    "cash": "Cash ran out and the bills could not be paid.",
    "health": "Repeated health-code failures forced the cart to close.",
}

# stats tracked (see sim.py stats dict)
STAT_KEYS = [
    "days", "revenue", "profit", "expenses", "customers", "repeat_customers",
    "sold", "lost_sales", "bought_units", "ad_spend", "travel_distance",
    "loans_taken", "interest_paid", "taxes_paid", "spoiled_units",
    "recipes_created", "batches", "districts_visited", "events_survived",
    "best_day_profit", "best_day_revenue",
]
