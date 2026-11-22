# Computes the paper's numbers that come from R. numbers_build.py runs this script and writes the
# macros and the ledger (research-kit languages spec §5). Running it directly stops with an error.
# Run: "{{KIT}}" numbers_build.py --project .
emit <- Sys.getenv("KIT_NUMBERS_EMIT")
if (!nzchar(emit)) stop("run this script through numbers_build.py, which sets KIT_NUMBERS_EMIT", call. = FALSE)
source(emit)

entries <- list(
  # list(name = "coverageMain", value = read.csv("analysis/sims/summary.csv")$coverage[1],
  #      format = "%.2f", src = "analysis/sims/summary.csv")
)

emit_numbers(entries)
