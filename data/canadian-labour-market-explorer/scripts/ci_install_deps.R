# CI dependency installer. Uses Posit Package Manager so Ubuntu runners get
# prebuilt binaries instead of compiling from source.
options(
  repos = c(CRAN = "https://packagemanager.posit.co/cran/latest"),
  HTTPUserAgent = sprintf(
    "R/%s R (%s)",
    getRversion(),
    paste(getRversion(), R.version["platform"], R.version["arch"], R.version["os"])
  )
)
install.packages(c("testthat", "jsonlite"))
