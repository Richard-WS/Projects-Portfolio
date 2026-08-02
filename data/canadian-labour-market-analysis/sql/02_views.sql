-- ============================================================================
-- Canadian Labour Market Analysis — analytical views
--
-- Views are the warehouse's "standard questions": each one pins down a
-- recurring slice of the data (a characteristic, an age group, a gender) so
-- the query catalog and any ad-hoc exploration start from a consistent
-- definition. All of them filter to the total-gender, 15-years-and-over
-- population unless the view name says otherwise.
-- ============================================================================

-- Unemployment rate (%), 15+, both genders combined — the headline indicator.
CREATE VIEW IF NOT EXISTS v_unemployment_rate AS
SELECT ref_year, region_code, value AS unemployment_rate_pct
FROM labour_force
WHERE characteristic = 'Unemployment rate'
  AND age_group      = '15 years and over'
  AND gender         = 'Total';

-- Employment rate (%), 15+ — share of the 15+ population that is employed.
CREATE VIEW IF NOT EXISTS v_employment_rate AS
SELECT ref_year, region_code, value AS employment_rate_pct
FROM labour_force
WHERE characteristic = 'Employment rate'
  AND age_group      = '15 years and over'
  AND gender         = 'Total';

-- Employment level (thousands), 15+ — the absolute jobs count.
CREATE VIEW IF NOT EXISTS v_employment AS
SELECT ref_year, region_code, value AS employment_thousands
FROM labour_force
WHERE characteristic = 'Employment'
  AND age_group      = '15 years and over'
  AND gender         = 'Total';

-- Participation rate (%), 15+ — labour-force members as a share of population.
CREATE VIEW IF NOT EXISTS v_participation_rate AS
SELECT ref_year, region_code, value AS participation_rate_pct
FROM labour_force
WHERE characteristic = 'Participation rate'
  AND age_group      = '15 years and over'
  AND gender         = 'Total';

-- Participation rate by gender, 15+ — feeds the gender-gap analysis.
CREATE VIEW IF NOT EXISTS v_participation_by_gender AS
SELECT ref_year, region_code, gender, value AS participation_pct
FROM labour_force
WHERE characteristic = 'Participation rate'
  AND age_group      = '15 years and over';

-- Working-age population (15-64), both genders combined, persons.
-- The labour table has no "All ages" row, so 15-64 is the closest full
-- working-age denominator for per-capita comparisons.
CREATE VIEW IF NOT EXISTS v_working_age_pop AS
SELECT ref_year, region_code, value AS population_15_64
FROM population
WHERE age_group = '15 to 64 years'
  AND gender    = 'Total';

-- Jobs per 1,000 working-age people: joins the labour and population fact
-- tables on (ref_year, region_code). Employment is stored in thousands and
-- population in persons, so employment is scaled to persons first, then the
-- ratio is scaled to per-1,000 (1,000,000 = 1,000 * 1,000).
CREATE VIEW IF NOT EXISTS v_employment_per_capita AS
SELECT e.ref_year,
       e.region_code,
       e.employment_thousands * 1000000.0 / NULLIF(p.population_15_64, 0)
           AS employed_per_1000_working_age
FROM v_employment e
JOIN v_working_age_pop p USING (ref_year, region_code);

-- Part-time employment as a share of total employment (%), 15+.
CREATE VIEW IF NOT EXISTS v_part_time_share AS
SELECT ref_year, region_code, value AS part_time_share_pct
FROM labour_force
WHERE characteristic = 'Proportion employed part-time'
  AND age_group      = '15 years and over'
  AND gender         = 'Total';
