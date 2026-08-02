# analysis_functions.R — pure, testable functions for the labour-market explorer.
#
# Design: no side effects, no file I/O, base R only. Every function takes a
# data frame and returns a data frame / list, so the testthat suite can cover
# them with hand-computable fixtures.

# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

#' Read the annual labour-market sample CSV.
#'
#' Columns: year, region_code, region_name, unemployment_rate,
#' employment_thousands, participation_rate, youth_unemployment_rate,
#' prime_age_unemployment_rate. Numeric columns are coerced with an explicit
#' na.strings list so suppressed StatsCan cells never become strings.
read_labour_data <- function(path) {
  df <- read.csv(
    path,
    stringsAsFactors = FALSE,
    na.strings = c("NA", "", "..", "F", "...")
  )
  numeric_cols <- c(
    "unemployment_rate", "employment_thousands", "participation_rate",
    "youth_unemployment_rate", "prime_age_unemployment_rate"
  )
  for (col in numeric_cols) {
    df[[col]] <- as.numeric(df[[col]])
  }
  df
}

# ---------------------------------------------------------------------------
# Time-series helpers
# ---------------------------------------------------------------------------

#' Extract one region's time series, sorted by year.
region_series <- function(df, region_code) {
  s <- df[df$region_code == region_code, , drop = FALSE]
  s[order(s$year), , drop = FALSE]
}

#' Mean unemployment for a region across all years in a decade.
#' Decade label is derived from the year (floor(year / 10) * 10).
decade_mean <- function(df, region_code, decade_start) {
  in_decade <- df$region_code == region_code &
    floor(df$year / 10) * 10 == decade_start
  mean(df$unemployment_rate[in_decade], na.rm = TRUE)
}

#' NB vs Canada unemployment gap (percentage points) by decade.
#' Returns a data frame: decade, nb_unemployment, canada_unemployment, gap_pp.
decade_gap_table <- function(df) {
  years <- sort(unique(df$year))
  decade_starts <- sort(unique(floor(years / 10) * 10))
  gaps <- lapply(decade_starts, function(ds) {
    nb <- decade_mean(df, "NB", ds)
    ca <- decade_mean(df, "CA", ds)
    data.frame(
      decade = paste0(ds, "s"),
      decade_start = ds,
      nb_unemployment = nb,
      canada_unemployment = ca,
      gap_pp = round(nb - ca, 2)
    )
  })
  do.call(rbind, gaps)
}

#' Youth minus prime-age unemployment gap by year for a region.
youth_prime_gap <- function(df, region_code) {
  s <- region_series(df, region_code)
  data.frame(
    year = s$year,
    youth_unemployment = s$youth_unemployment_rate,
    prime_age_unemployment = s$prime_age_unemployment_rate,
    gap_pp = round(s$youth_unemployment_rate - s$prime_age_unemployment_rate, 2)
  )
}

#' Employment indexed to a base year (base = 100).
employment_index <- function(df, region_code, base_year) {
  s <- region_series(df, region_code)
  base <- s$employment_thousands[s$year == base_year]
  if (length(base) != 1 || is.na(base)) {
    return(rep(NA_real_, nrow(s)))
  }
  round(s$employment_thousands / base * 100, 1)
}

# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

#' Linear trend (slope per decade + r-squared) for a numeric column.
#' Returns a one-row data frame, or NA slope when the series is degenerate.
linear_trend <- function(df, region_code, column, per_year_col = "year") {
  s <- region_series(df, region_code)
  x <- s[[per_year_col]]
  y <- s[[column]]
  keep <- !is.na(x) & !is.na(y)
  x <- x[keep]
  y <- y[keep]
  if (length(unique(x)) < 2 || length(unique(y)) < 2) {
    return(data.frame(region_code = region_code, slope_pp_per_decade = NA_real_, r_squared = NA_real_))
  }
  fit <- lm(y ~ x)
  slope_per_year <- coef(fit)[["x"]]
  data.frame(
    region_code = region_code,
    slope_pp_per_decade = round(slope_per_year * 10, 3),
    r_squared = round(summary(fit)$r.squared, 4)
  )
}

trend_table <- function(df, column = "unemployment_rate") {
  regions <- sort(unique(df$region_code))
  do.call(rbind, lapply(regions, function(code) linear_trend(df, code, column)))
}

# ---------------------------------------------------------------------------
# Dashboard assembly
# ---------------------------------------------------------------------------

#' Build the complete dashboard JSON payload (a list, serializable by jsonlite).
build_dashboard_payload <- function(df, meta = NULL) {
  region_codes <- sort(unique(df$region_code))
  regions <- lapply(region_codes, function(code) {
    s <- region_series(df, code)
    list(
      code = code,
      name = s$region_name[1],
      series = lapply(seq_len(nrow(s)), function(i) {
        row <- s[i, ]
        list(
          year = row$year,
          unemploymentRate = row$unemployment_rate,
          employmentThousands = row$employment_thousands,
          participationRate = row$participation_rate,
          youthUnemploymentRate = row$youth_unemployment_rate,
          primeAgeUnemploymentRate = row$prime_age_unemployment_rate
        )
      })
    )
  })

  latest_year <- max(df$year)
  latest <- df[df$year == latest_year, , drop = FALSE]
  ca <- latest[latest$region_code == "CA", , drop = FALSE]
  nb <- latest[latest$region_code == "NB", , drop = FALSE]

  list(
    meta = meta,
    regions = regions,
    decades = decade_gap_table(df),
    trends = trend_table(df),
    highlights = list(
      latestYear = latest_year,
      canadaUnemploymentLatest = round(ca$unemployment_rate[1], 1),
      newBrunswickUnemploymentLatest = round(nb$unemployment_rate[1], 1),
      youthPrimeGapLatest = round(ca$youth_unemployment_rate[1] - ca$prime_age_unemployment_rate[1], 1)
    )
  )
}
