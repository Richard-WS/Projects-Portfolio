# Data projects

Data pipelines, analysis, and reporting — reproducible, documented, and covered by automated tests.

## Projects

- **[Canadian grocery inflation, 2015–2026](canadian-food-inflation/)** — how food prices have moved against overall inflation in Canada over the past decade, built on Statistics Canada CPI data (Table 18-10-0004-01). Includes a cleaning pipeline, exploratory analysis, a self-contained dashboard report, and unit-tested analysis code.
- **[Canadian labour market analysis](canadian-labour-market-analysis/)** — Statistics Canada labour force and population tables normalized into a SQLite warehouse, answered through a 14-query analytical SQL catalog. Reproducible Python ETL, 59 hermetic tests, and query results committed.
- **[Canadian labour market explorer](canadian-labour-market-explorer/)** — the warehouse's interactive companion: R computes unemployment, employment, and participation statistics for Canada and the provinces (1976–2025) and exports JSON; a zero-dependency JavaScript dashboard renders them with recession shading and hover readouts. Live on GitHub Pages.
