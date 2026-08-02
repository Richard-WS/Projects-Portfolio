# testthat runner. Invoked from the project root:
#   Rscript tests/testthat.R
library(testthat)
library(jsonlite)

source("R/analysis_functions.R")
test_dir("tests/testthat", reporter = "summary")
