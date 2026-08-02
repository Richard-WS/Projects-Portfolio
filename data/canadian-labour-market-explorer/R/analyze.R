# analyze.R — run the full analysis on the committed sample and write the
# dashboard payload (docs/results/data.json) plus report charts
# (docs/results/charts/*.png).
#
# Usage: Rscript R/analyze.R   (from the project root)

source("R/analysis_functions.R")
library(jsonlite)

project_root <- normalizePath(".")
sample_path <- file.path(project_root, "data", "samples", "labour_market_annual.csv")
results_dir <- file.path(project_root, "docs", "results")
charts_dir <- file.path(results_dir, "charts")
dir.create(results_dir, showWarnings = FALSE, recursive = TRUE)
dir.create(charts_dir, showWarnings = FALSE, recursive = TRUE)

df <- read_labour_data(sample_path)
cat(sprintf("Read %d rows (%d years x %d regions)\n", nrow(df),
            length(unique(df$year)), length(unique(df$region_code))))

meta <- list(
  title = "Canadian Labour Market Explorer",
  source = "Statistics Canada Table 14-10-0327-01 (Labour force characteristics, annual)",
  licence = "Statistics Canada Open Licence",
  period = paste0(min(df$year), "-", max(df$year)),
  generated = format(Sys.Date(), "%Y-%m-%d"),
  regions = length(unique(df$region_code))
)

payload <- build_dashboard_payload(df, meta)
writeLines(toJSON(payload, auto_unbox = TRUE, digits = 6, pretty = TRUE),
           file.path(results_dir, "data.json"))
cat("Wrote docs/results/data.json\n")

# ---------------------------------------------------------------------------
# Report charts (base R graphics)
# ---------------------------------------------------------------------------

key_regions <- c("CA", "NB", "ON", "AB", "NL")
col_for <- c(CA = "#1f77b4", NB = "#d62728", ON = "#2ca02c",
             AB = "#ff7f0e", NL = "#9467bd")

png(file.path(charts_dir, "unemployment_by_region.png"),
    width = 900, height = 560, res = 110)
par(mar = c(4.5, 4.5, 3, 1))
yrs <- sort(unique(df$year))
plot(range(yrs), range(df$unemployment_rate[df$region_code %in% key_regions],
                       na.rm = TRUE),
     type = "n", xlab = "Year", ylab = "Unemployment rate (%)",
     main = "Unemployment rate by region, 1976-2025")
grid()
for (code in key_regions) {
  s <- region_series(df, code)
  lines(s$year, s$unemployment_rate, col = col_for[[code]], lwd = 2)
}
legend("topright", legend = names(col_for), col = unname(col_for),
       lwd = 2, bty = "n", cex = 0.9)
mtext("Source: Statistics Canada Table 14-10-0327-01", side = 1, line = 3.2, cex = 0.7)
dev.off()

png(file.path(charts_dir, "nb_vs_canada_gap.png"),
    width = 900, height = 560, res = 110)
par(mar = c(4.5, 4.5, 3, 1))
ca <- region_series(df, "CA")
nb <- region_series(df, "NB")
plot(ca$year, ca$unemployment_rate, type = "l", col = "#1f77b4", lwd = 2,
     ylim = range(c(ca$unemployment_rate, nb$unemployment_rate), na.rm = TRUE),
     xlab = "Year", ylab = "Unemployment rate (%)",
     main = "New Brunswick vs Canada: the narrowing gap")
grid()
lines(nb$year, nb$unemployment_rate, col = "#d62728", lwd = 2)
polygon(c(nb$year, rev(ca$year)),
        c(nb$unemployment_rate, rev(ca$unemployment_rate)),
        col = rgb(0.84, 0.15, 0.16, 0.12), border = NA)
legend("topright", legend = c("Canada", "New Brunswick", "Gap"),
       col = c("#1f77b4", "#d62728", NA), fill = c(NA, NA, rgb(0.84, 0.15, 0.16, 0.12)),
       border = NA, lwd = c(2, 2, NA), bty = "n", cex = 0.9)
mtext("Shaded area is the NB-Canada unemployment gap", side = 1, line = 3.2, cex = 0.7)
dev.off()

png(file.path(charts_dir, "youth_vs_prime.png"),
    width = 900, height = 560, res = 110)
par(mar = c(4.5, 4.5, 3, 1))
yg <- youth_prime_gap(df, "CA")
plot(yg$year, yg$youth_unemployment, type = "l", col = "#ff7f0e", lwd = 2,
     ylim = range(c(yg$youth_unemployment, yg$prime_age_unemployment), na.rm = TRUE),
     xlab = "Year", ylab = "Unemployment rate (%)",
     main = "Canada: youth (15-24) vs prime-age (25-54) unemployment")
grid()
lines(yg$year, yg$prime_age_unemployment, col = "#2ca02c", lwd = 2)
legend("topright", legend = c("Youth 15-24", "Prime-age 25-54"),
       col = c("#ff7f0e", "#2ca02c"), lwd = 2, bty = "n", cex = 0.9)
mtext("Source: Statistics Canada Table 14-10-0327-01", side = 1, line = 3.2, cex = 0.7)
dev.off()

cat("Wrote docs/results/charts/*.png (3 charts)\n")
cat("Done.\n")
