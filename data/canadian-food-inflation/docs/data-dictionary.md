# Data dictionary — cpi_canada_food_2015_2026.csv

Tidy long-format subset of Statistics Canada Table 18-10-0004-01 (Consumer Price Index, monthly, not seasonally adjusted).

## Columns

| Column | Type | Description |
|---|---|---|
| `date` | date (YYYY-MM-01) | First day of the reference month |
| `product` | str | Product group (see values below) |
| `value` | float | CPI index level, base **2002=100** |
| `yoy` | float | Year-over-year percent change vs same month last year (NaN for first 12 months of each product) |

## Product groups (5)

- `All-items` — the full CPI basket
- `Food purchased from stores` — groceries
- `Food purchased from restaurants` — dining out
- `Fresh vegetables`
- `Fresh fruit`

## Scope

- Geography: **Canada** only
- Index base: **2002=100** (all five series share this base, so levels are directly comparable)
- Period: **2015-01 to 2026-06** (138 months × 5 products = 690 rows)

## Source

Statistics Canada, Table 18-10-0004-01:
https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
