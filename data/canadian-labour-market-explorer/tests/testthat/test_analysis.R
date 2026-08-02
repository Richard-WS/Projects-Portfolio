# Tests for analysis_functions.R against a hand-computable fixture
# (tests/fixtures/tiny_labour.csv: CA, NB, ON x 2000-2003).

fixture <- read_labour_data(test_path("fixtures/tiny_labour.csv"))

test_that("read_labour_data loads numeric columns", {
  expect_equal(nrow(fixture), 12)
  expect_equal(ncol(fixture), 8)
  expect_type(fixture$unemployment_rate, "double")
  expect_type(fixture$year, "integer")
})

test_that("region_series filters and sorts by year", {
  ca <- region_series(fixture, "CA")
  expect_equal(nrow(ca), 4)
  expect_true(all(ca$region_code == "CA"))
  expect_equal(ca$year, 2000:2003)
  expect_equal(ca$region_name[1], "Canada")
})

test_that("decade_gap_table computes the NB-Canada gap", {
  gaps <- decade_gap_table(fixture)
  expect_equal(nrow(gaps), 1)                 # single decade: 2000s
  expect_equal(gaps$decade, "2000s")
  expect_equal(gaps$nb_unemployment, 9.0)     # flat 9.0
  expect_equal(gaps$canada_unemployment, 6.75)  # (6+6.5+7+7.5)/4
  expect_equal(gaps$gap_pp, 2.25)
})

test_that("youth_prime_gap subtracts prime-age from youth", {
  yg <- youth_prime_gap(fixture, "CA")
  expect_equal(nrow(yg), 4)
  expect_equal(yg$gap_pp, rep(7.0, 4))        # 12 - 5
})

test_that("employment_index indexes to the base year", {
  idx <- employment_index(fixture, "CA", 2000)
  expect_equal(idx, c(100.0, 101.0, 102.0, 103.0))
})

test_that("linear_trend recovers the exact slope on linear data", {
  ca <- linear_trend(fixture, "CA", "unemployment_rate")
  expect_equal(ca$slope_pp_per_decade, 5.0)   # 0.5 pp/year x 10
  expect_equal(ca$r_squared, 1.0)
  nb <- linear_trend(fixture, "NB", "unemployment_rate")
  expect_true(is.na(nb$slope_pp_per_decade))  # degenerate flat series
})

test_that("trend_table covers every region", {
  t <- trend_table(fixture)
  expect_equal(sort(t$region_code), c("CA", "NB", "ON"))
})

test_that("build_dashboard_payload assembles the full structure", {
  p <- build_dashboard_payload(fixture, meta = list(title = "test"))
  expect_equal(length(p$regions), 3)
  expect_equal(length(p$regions[[1]]$series), 4)
  expect_equal(p$highlights$latestYear, 2003)
  expect_equal(p$highlights$canadaUnemploymentLatest, 7.5)
  expect_equal(p$highlights$youthPrimeGapLatest, 7.0)
  expect_equal(p$decades$gap_pp, 2.25)
})

test_that("payload serializes to valid JSON", {
  p <- build_dashboard_payload(fixture, meta = list(title = "test"))
  json <- toJSON(p, auto_unbox = TRUE, digits = 6)
  expect_true(nchar(json) > 100)
  parsed <- fromJSON(json)
  expect_equal(parsed$highlights$latestYear, 2003)
})
