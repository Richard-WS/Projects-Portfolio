# Richard Seyeau

Data analytics, business intelligence, and IT service management professional. Open to remote and hybrid roles in data, AI, IT, and tech — including the Canadian federal government and data centre operations.

## About

I work across the data lifecycle: cleaning and validating data, analysing it with statistics and machine-learning methods, and presenting it through dashboards and reports that non-technical stakeholders can act on. I hold professional certificates in data analytics (Google, IBM), statistics (Wolfram), Power BI (Microsoft), and ITIL 4 service management, and I keep building on that foundation through applied projects — the ones in this repo are documented, tested, and reproducible.

## Skills

| Area | Skills |
|---|---|
| Data analysis | Exploratory analysis, data cleaning, transformation, validation, modelling, predictive analytics, regression |
| BI & reporting | Power BI, Tableau, Excel, IBM Cognos Analytics, dashboards, report writing, data storytelling |
| Programming & databases | Python, Pandas, NumPy, Polars, DuckDB, SQL, R, PostgreSQL, MySQL, MongoDB, GraphQL, Jupyter |
| Statistics & ML | Descriptive and inferential statistics, probability, hypothesis testing, ANOVA, regression, supervised and unsupervised learning, model interpretation |
| IT service management | ITIL 4 Foundation — service value system, governance, continual improvement |
| Data quality & governance | Metadata management, documentation, integrity checks, privacy-aware handling of information |
| Tools | Visual Studio Code, Git/GitHub, RStudio, Google Colab, Power Query, Microsoft Access |

## Certifications

- **Advanced Data Analytics Professional Certificate** — Google, 2024–2025
- **Statistics Foundations Professional Certificate** — Wolfram Research, 2024
- **Data Analytics Professional Certificate** — Google, 2024
- **ITIL 4 Foundation** — AXELOS / PeopleCert, 2024
- **Microsoft Power BI Data Analyst Professional Certificate** — Microsoft, 2023
- **Data Analyst Professional Certificate** — IBM, 2023
- **Programming certificates** (Python, SQL, PostgreSQL, MongoDB, GraphQL, RDBMS, data science) — Programming Hub, 2019–ongoing

## Experience highlights

- **Owner/Operator, Keirstead Manor Bed & Breakfast** (2017–2020) — ran daily guest operations and service delivery; built booking and guest-profile databases in Access, Excel, and Memento to track reservations and personalise service; maintained a 9.9/10 guest rating.
- **Citizen-science classifier, Zooniverse** (2024–ongoing) — classifies SuperWASP stellar light curves and reviews NGTS exoplanet-transit candidates: pattern recognition and time-series review on real scientific data.

## Featured projects

- **[Exoplanet transit classifier](ai-ml/exoplanet-transit-classifier/)** — 0.946 cross-validated ROC-AUC on 5,000+ Kepler light curves, zero false positives on the held-out test set. The same transit-hunting pattern I do on Zooniverse, made reproducible.

- **[LLM fine-tuning workflow](ai-ml/llm-fine-tuning-workflow/)** — LoRA fine-tuning on a laptop CPU, validation perplexity 39.8 → 22.0. Config-driven, tested, documented end to end.

- **[Infrastructure health monitor](it-ops/infra-health-monitor/)** — SLO tracking with four check types, transition and breach alerts, self-contained HTML reports. Live demo caught a flaky service and a crashed worker.

- **[Canadian grocery inflation](data/canadian-food-inflation/)** — ten years of StatsCan CPI data showing groceries outrunning overall inflation (+43.4% vs +36.0%), with an EDA notebook and self-contained dashboard.

- **[Canadian labour market analysis](data/canadian-labour-market-analysis/)** — Statistics Canada labour force and population tables normalized into a SQLite warehouse, answered through a 14-query SQL catalog. New Brunswick's unemployment gap versus Canada narrowed from 4.2 pp (1970s) to 1.1 pp (2020s).

- **[Query engine benchmark](experiments/query-engine-benchmark/)** — pandas, Polars, and DuckDB on 5M orders with cross-engine result verification. DuckDB was 5–28× faster than pandas on most queries with ~2.2× less peak memory; Polars won load time and group-bys.

- **[Solar system positions viewer](experiments/solar-system-positions/)** — an interactive 2D scatter-plot model of the solar system: every planet's position for every month 1900–2100, computed with Astropy's built-in ephemeris and viewable as a self-contained HTML timeline on GitHub Pages.

## Repo layout

| Folder | Contents |
|---|---|
| `data/` | Data pipelines, analysis, and reporting — [Canadian grocery inflation project](data/canadian-food-inflation/), [Canadian labour market analysis](data/canadian-labour-market-analysis/) |
| `ai-ml/` | Machine learning and AI applications — [LLM fine-tuning workflow](ai-ml/llm-fine-tuning-workflow/), [exoplanet transit classifier](ai-ml/exoplanet-transit-classifier/) |
| `it-ops/` | Infrastructure, automation, and operations — [infrastructure health monitor](it-ops/infra-health-monitor/) |
| `experiments/` | Prototypes, tools, and personal projects — [query engine benchmark](experiments/query-engine-benchmark/), [solar system positions viewer](experiments/solar-system-positions/) |
| `docs/` | Project standards and skills matrix |

## Contact

- LinkedIn: [linkedin.com/in/richard-w-seyeau](https://linkedin.com/in/richard-w-seyeau)
- GitHub: [github.com/Richard-WS](https://github.com/Richard-WS)
