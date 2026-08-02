-- ============================================================================
-- Canadian Labour Market Analysis — query catalog
--
-- Fourteen named analytical queries. Each block starts with a header the
-- catalog loader parses:
--
--     -- query: <name>        unique identifier (the CLI runs queries by name)
--     -- title: ...           short human-readable title
--     -- question: ...        what the query answers in plain language
--     -- technique: ...       which SQL techniques the query demonstrates
--
-- Every query runs against the schema (01_schema.sql) and views
-- (02_views.sql). Results are deterministic: same database, same rows.
-- ============================================================================


-- ============================================================================
-- query: q01_unemployment_national
-- title: National unemployment trend, 1976-2025
-- question: How has Canada's unemployment rate moved over the five decades?
-- technique: Simple filter + sort on the unemployment-rate view — the
--            catalog's baseline query and a sanity check for the rest.
-- ============================================================================
SELECT ref_year,
       ROUND(unemployment_rate_pct, 1) AS unemployment_pct
FROM v_unemployment_rate
WHERE region_code = 'CA'
ORDER BY ref_year;


-- ============================================================================
-- query: q02_unemployment_by_province_latest
-- title: Provincial unemployment and employment rates, latest year
-- question: Which provinces had the highest and lowest unemployment in 2025,
--           and how does employment rate vary with it?
-- technique: Correlated subquery picks the latest available year so the query
--            never goes stale when the source table is refreshed; the two
--            rate views are joined on (year, region).
-- ============================================================================
SELECT r.region_name,
       ur.unemployment_rate_pct,
       er.employment_rate_pct
FROM v_unemployment_rate ur
JOIN v_employment_rate   er USING (ref_year, region_code)
JOIN regions             r  ON r.region_code = ur.region_code
WHERE ur.ref_year = (SELECT MAX(ref_year) FROM v_unemployment_rate)
  AND ur.region_code <> 'CA'
ORDER BY ur.unemployment_rate_pct DESC;


-- ============================================================================
-- query: q03_employment_growth_yoy
-- title: Canada employment growth, year over year
-- question: In which years did national employment grow or shrink fastest?
-- technique: Window function LAG() over the ordered year series computes
--            year-over-year growth; the 1976 row correctly shows NULL.
-- ============================================================================
SELECT ref_year,
       ROUND(employment_thousands, 1) AS employment_k,
       ROUND(100.0 * (employment_thousands / LAG(employment_thousands) OVER (ORDER BY ref_year) - 1), 2)
           AS yoy_growth_pct
FROM v_employment
WHERE region_code = 'CA'
ORDER BY ref_year;


-- ============================================================================
-- query: q04_provincial_employment_share
-- title: Each province's share of national employment, 1976 vs 2025
-- question: How has the geographic centre of gravity of Canadian jobs moved?
-- technique: CTE computes the provincial total per year (Canada itself is
--            excluded from the denominator); the comparison is a classic
--            two-period share analysis.
-- ============================================================================
WITH provincial_totals AS (
    SELECT ref_year, SUM(employment_thousands) AS total_k
    FROM v_employment
    WHERE region_code <> 'CA'
    GROUP BY ref_year
)
SELECT r.region_name,
       e.ref_year,
       ROUND(e.employment_thousands, 1)           AS employment_k,
       ROUND(100.0 * e.employment_thousands / t.total_k, 2) AS share_pct
FROM v_employment e
JOIN provincial_totals t USING (ref_year)
JOIN regions r ON r.region_code = e.region_code
WHERE e.ref_year IN (1976, 2025)
  AND e.region_code <> 'CA'
ORDER BY e.ref_year, share_pct DESC;


-- ============================================================================
-- query: q05_fastest_growing_provinces
-- title: Fastest-growing provinces by employment, 2000 to 2025
-- question: Which provinces created jobs fastest over the past quarter century?
-- technique: Conditional aggregation (MAX(CASE ...)) inside a CTE turns the
--            long-format table into a two-column comparison without a join.
-- ============================================================================
WITH endpoints AS (
    SELECT region_code,
           MAX(CASE WHEN ref_year = 2000 THEN employment_thousands END) AS emp_2000_k,
           MAX(CASE WHEN ref_year = 2025 THEN employment_thousands END) AS emp_2025_k
    FROM v_employment
    WHERE region_code <> 'CA'
    GROUP BY region_code
)
SELECT r.region_name,
       ROUND(emp_2000_k, 1)                        AS emp_2000_k,
       ROUND(emp_2025_k, 1)                        AS emp_2025_k,
       ROUND(100.0 * (emp_2025_k / emp_2000_k - 1), 1) AS growth_pct
FROM endpoints
JOIN regions r ON r.region_code = endpoints.region_code
ORDER BY growth_pct DESC;


-- ============================================================================
-- query: q06_recession_2008_recovery
-- title: Canada employment through the 2008-09 recession
-- question: How deep was the 2008-09 employment dip, and how long did
--           recovery take to pass the pre-recession peak?
-- technique: CTE holds the pre-2009 peak; the main query subtracts it from
--            every year's level so the dip and recovery read directly in
--            thousands of jobs relative to that peak.
-- ============================================================================
WITH pre_recession_peak AS (
    SELECT MAX(employment_thousands) AS peak_k
    FROM v_employment
    WHERE region_code = 'CA' AND ref_year <= 2008
)
SELECT e.ref_year,
       ROUND(e.employment_thousands, 1)          AS employment_k,
       ROUND(e.employment_thousands - p.peak_k, 1) AS vs_peak_k
FROM v_employment e, pre_recession_peak p
WHERE e.region_code = 'CA' AND e.ref_year BETWEEN 2006 AND 2012
ORDER BY e.ref_year;


-- ============================================================================
-- query: q07_covid_shock_2020
-- title: Provincial employment through the 2020 COVID shock
-- question: Which provinces lost and regained the most jobs in 2020-2021?
-- technique: Pivot via conditional aggregation over the three years, then a
--            computed change column for 2019 -> 2021 in percent.
-- ============================================================================
SELECT region_code,
       ROUND(MAX(CASE WHEN ref_year = 2019 THEN employment_thousands END), 1) AS emp_2019_k,
       ROUND(MAX(CASE WHEN ref_year = 2020 THEN employment_thousands END), 1) AS emp_2020_k,
       ROUND(MAX(CASE WHEN ref_year = 2021 THEN employment_thousands END), 1) AS emp_2021_k,
       ROUND(100.0 * (MAX(CASE WHEN ref_year = 2021 THEN employment_thousands END)
                    / MAX(CASE WHEN ref_year = 2019 THEN employment_thousands END) - 1), 2)
           AS pct_change_2019_2021
FROM v_employment
WHERE region_code <> 'CA'
GROUP BY region_code
ORDER BY pct_change_2019_2021;


-- ============================================================================
-- query: q08_nb_vs_canada_unemployment
-- title: New Brunswick vs Canada unemployment, by decade
-- question: How far has New Brunswick's unemployment rate sat above (or
--           below) the national average, decade by decade?
-- technique: AVG with a CASE filter per region inside one GROUP BY — a
--            self-contained gap calculation with no self-join.
-- ============================================================================
SELECT (ref_year / 10) * 10 AS decade,
       ROUND(AVG(CASE WHEN region_code = 'NB' THEN unemployment_rate_pct END), 2) AS nb_avg_pct,
       ROUND(AVG(CASE WHEN region_code = 'CA' THEN unemployment_rate_pct END), 2) AS canada_avg_pct,
       ROUND(AVG(CASE WHEN region_code = 'NB' THEN unemployment_rate_pct END)
            - AVG(CASE WHEN region_code = 'CA' THEN unemployment_rate_pct END), 2) AS gap_pp
FROM v_unemployment_rate
WHERE region_code IN ('NB', 'CA')
GROUP BY decade
ORDER BY decade;


-- ============================================================================
-- query: q09_unemployment_moving_average
-- title: Canada unemployment rate, 5-year centred moving average
-- question: What is the smoothed long-run unemployment trend, free of
--           single-year noise like 1982 or 2020?
-- technique: Window function with ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING
--            computes a centred moving average; endpoints use fewer rows.
-- ============================================================================
SELECT ref_year,
       ROUND(unemployment_rate_pct, 2) AS unemployment_pct,
       ROUND(AVG(unemployment_rate_pct) OVER (ORDER BY ref_year ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING), 2)
           AS moving_average_5yr
FROM v_unemployment_rate
WHERE region_code = 'CA'
ORDER BY ref_year;


-- ============================================================================
-- query: q10_employment_per_working_age
-- title: Jobs per 1,000 working-age people, 1976 vs 2025
-- question: Beyond the unemployment rate, how many jobs exist relative to the
--           working-age population, and how has that changed per province?
-- technique: The v_employment_per_capita view joins the labour-force and
--            population fact tables on the shared age vocabulary — the
--            warehouse's cross-table payoff.
-- ============================================================================
SELECT r.region_name,
       vp.ref_year,
       ROUND(vp.employed_per_1000_working_age, 1) AS employed_per_1000
FROM v_employment_per_capita vp
JOIN regions r ON r.region_code = vp.region_code
WHERE vp.ref_year IN (1976, 2025)
  AND vp.region_code <> 'CA'
ORDER BY vp.ref_year, employed_per_1000 DESC;


-- ============================================================================
-- query: q11_gender_participation_gap
-- title: Participation rate by gender, Canada 1976 / 2000 / 2025
-- question: How has the men-vs-women participation gap narrowed over time?
-- technique: Conditional aggregation pivots the gender rows into columns and
--            computes the gap in percentage points in the same SELECT.
-- ============================================================================
SELECT ref_year,
       ROUND(MAX(CASE WHEN gender = 'Men+'   THEN participation_pct END), 1) AS men_pct,
       ROUND(MAX(CASE WHEN gender = 'Women+' THEN participation_pct END), 1) AS women_pct,
       ROUND(MAX(CASE WHEN gender = 'Men+'   THEN participation_pct END)
            - MAX(CASE WHEN gender = 'Women+' THEN participation_pct END), 1) AS gap_pp
FROM v_participation_by_gender
WHERE region_code = 'CA'
  AND ref_year IN (1976, 2000, 2025)
GROUP BY ref_year
ORDER BY ref_year;


-- ============================================================================
-- query: q12_youth_unemployment
-- title: Youth vs prime-age unemployment, Canada
-- question: How much higher has the 15-24 unemployment rate run than the
--           25-54 rate, and has the gap narrowed?
-- technique: Pivot of two age groups from the raw fact table with an IN
--            filter; each row is one year, each column one age group.
-- ============================================================================
SELECT ref_year,
       ROUND(MAX(CASE WHEN age_group = '15 to 24 years' THEN value END), 1) AS youth_15_24_pct,
       ROUND(MAX(CASE WHEN age_group = '25 to 54 years' THEN value END), 1) AS prime_25_54_pct,
       ROUND(MAX(CASE WHEN age_group = '15 to 24 years' THEN value END)
            - MAX(CASE WHEN age_group = '25 to 54 years' THEN value END), 1) AS gap_pp
FROM labour_force
WHERE region_code = 'CA'
  AND gender = 'Total'
  AND characteristic = 'Unemployment rate'
  AND age_group IN ('15 to 24 years', '25 to 54 years')
GROUP BY ref_year
ORDER BY ref_year;


-- ============================================================================
-- query: q13_part_time_share
-- title: Part-time share of employment by province, latest year
-- question: Which provinces rely most on part-time employment?
-- technique: Direct use of StatsCan's "Proportion employed part-time"
--            characteristic with a region-name join, ranked descending.
-- ============================================================================
SELECT r.region_name,
       ROUND(pt.part_time_share_pct, 2) AS part_time_share_pct
FROM v_part_time_share pt
JOIN regions r ON r.region_code = pt.region_code
WHERE pt.ref_year = (SELECT MAX(ref_year) FROM v_part_time_share)
  AND pt.region_code <> 'CA'
ORDER BY part_time_share_pct DESC;


-- ============================================================================
-- query: q14_nb_employment_by_decade
-- title: New Brunswick employment by decade
-- question: How has New Brunswick's employment base changed decade by decade?
-- technique: Decade bucketing with (ref_year / 10) * 10 and aggregate
--            summary columns (average, peak, trough) per bucket.
-- ============================================================================
SELECT (ref_year / 10) * 10 AS decade,
       ROUND(AVG(employment_thousands), 1) AS avg_employment_k,
       ROUND(MAX(employment_thousands), 1) AS peak_employment_k,
       ROUND(MIN(employment_thousands), 1) AS trough_employment_k
FROM v_employment
WHERE region_code = 'NB'
GROUP BY decade
ORDER BY decade;
