# Runs the R table writer on the shared cases (tests/fixtures/tex_tables_cases.csv) and two whole tables, for
# tests/python/test_tex_tables.py, which runs the Python writer the same way and compares the text.
# Usage: Rscript --vanilla tex_tables_cases.R <tex_tables.R> <cases.csv> <out file>, from a project folder whose
# analysis/params.R reads the style's analysis/params.yml.
args <- commandArgs(trailingOnly = TRUE)
source("analysis/params.R")
source(args[[1]])
style <- table_style(param)
cases <- read.csv(args[[2]], colClasses = "character", na.strings = character(), check.names = FALSE)
value <- function(s) if (identical(s, "NA")) NA else if (nzchar(s)) as.numeric(s) else NULL
one <- function(r) {
  d <- value(r[["decimals"]])
  plus <- identical(r[["plus"]], "TRUE")
  switch(r[["fn"]],
         number = tex_number(value(r[["a"]]), style, decimals = d, plus = plus, prefix = r[["prefix"]],
                             suffix = r[["suffix"]]),
         se = se_cell(value(r[["a"]]), style, decimals = d),
         interval = interval_cell(value(r[["a"]]), value(r[["b"]]), style, decimals = d),
         p = p_cell(value(r[["a"]]), style),
         star = star_marker(value(r[["a"]]), style),
         legend = star_legend(style))
}
out <- vapply(seq_len(nrow(cases)), function(i) {
  r <- as.list(cases[i, ])
  got <- tryCatch(one(r), error = function(e) "ERROR")
  paste0(r[["case"]], "\t", gsub("\n", "\\n", got, fixed = TRUE))
}, "")
band <- header_band(list(list(label = "Outcome A", first = "a1", last = "a2"),
                         list(label = "Outcome B", first = "b1", last = "b1")), c("a1", "a2", "b1", "n"))
rows <- c(band[[1]], band[[2]], table_row(c("", "(1)", "(2)", "(3)", "N")), "\\midrule",
          table_row(c("Treated", paste0(tex_number(-0.1234, style), star_marker(0.004, style)),
                      tex_number(0.0004, style), paste0(tex_number(2.5, style), star_marker(0.2, style)),
                      tex_number(12345, style, decimals = 0))),
          table_row(c("", se_cell(0.05, style), se_cell(0.0001, style), se_cell(NA, style), "")),
          table_row(c("95\\% CI", interval_cell(-0.2, -0.04, style), interval_cell(-0.0004, 0.1, style),
                      interval_cell(1, 4, style), "")),
          table_row(c("p", p_cell(0.004, style), p_cell(0.0996, style), p_cell(0.5, style), "")))
float <- tex_table("lcccc", rows, style, caption = "Main results.", label = "tab:main",
                   notes = "Standard errors in brackets.", landscape = TRUE)
fragment <- tex_table("lcccc", rows[-c(1, 2)], style)
plain <- tex_table("lc", table_row(c("Mean", tex_number(1.5, style))), style)
out <- c(out, paste0("float\t", gsub("\n", "\\n", float, fixed = TRUE)),
         paste0("fragment\t", gsub("\n", "\\n", fragment, fixed = TRUE)),
         paste0("plain\t", gsub("\n", "\\n", plain, fixed = TRUE)))
con <- file(args[[3]], open = "wb")
writeBin(charToRaw(enc2utf8(paste0(paste(out, collapse = "\n"), "\n"))), con)
close(con)
