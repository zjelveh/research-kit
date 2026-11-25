# Computes the paper's numbers that come from R. numbers_build.py runs this script and writes the
# macros and the ledger (research-kit languages spec §5). Running it directly stops with an error.
# Run: "{{KIT}}" numbers_build.py --project .
emit <- Sys.getenv("KIT_NUMBERS_EMIT")
if (!nzchar(emit)) stop("run this script through numbers_build.py, which sets KIT_NUMBERS_EMIT", call. = FALSE)
source(emit)
source("analysis/params.R")  # param("name") reads analysis/params.yml (/kit:code): paths are never typed here

entries <- list(
  # list(name = "coverageMain", value = read.csv(param("sims_summary"))$coverage[1],
  #      format = "%.2f", src = param("sims_summary"))
)

emit_numbers(entries)
